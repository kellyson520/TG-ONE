import asyncio
import logging
from typing import Dict, Any, Tuple

from core.container import container
from core.helpers.time_range import parse_time_range_to_dates

logger = logging.getLogger(__name__)


class SessionDedupMixin:
    """消息去重扫描与删除相关方法"""

    async def scan_duplicate_messages(self, event, progress_callback=None):
        chat_id = event.chat_id
        user_id = event.sender_id
        cached_result = self._get_cached_scan_result(chat_id)
        if not progress_callback and cached_result:
            logger.info(f"💾 返回会话 {chat_id} 的去重扫描缓存结果")
            return cached_result
        time_config = self.get_time_range(chat_id)
        begin_date, end_date, _, _ = parse_time_range_to_dates(time_config)
        duplicates = {}
        seen_sigs = {}
        processed = 0
        client = container.user_client
        self._clear_scan_result(chat_id)
        try:
            async for message in client.iter_messages(chat_id, offset_date=begin_date, reverse=True):
                if end_date and message.date > end_date.replace(tzinfo=None):
                    break
                processed += 1
                from services.dedup import tools
                sig = tools.generate_content_hash(message)
                if not sig:
                    sig = tools.generate_signature(message)
                if sig:
                    if sig in seen_sigs:
                        if sig not in duplicates:
                            duplicates[sig] = []
                        duplicates[sig].append(message.id)
                    else:
                        seen_sigs[sig] = message.id
                if progress_callback and processed % 100 == 0:
                    await progress_callback(processed, len(duplicates))
            session = self._get_user_session(chat_id)
            sig_mapping = {}
            for sig in duplicates:
                import hashlib
                short_id = hashlib.md5(sig.encode()).hexdigest()[:8]
                sig_mapping[short_id] = sig
            session['sig_mapping'] = sig_mapping
            self._set_scan_result(chat_id, duplicates)
            logger.info(f"✅ 扫描完成: 处理 {processed} 条，发现 {len(duplicates)} 组重复内容 (映射数: {len(sig_mapping)})")
            return duplicates
        except Exception as e:
            logger.error(f"扫描重复消息失败: {e}", exc_info=True)
            return {}

    async def delete_duplicate_messages(self, event, mode="all"):
        chat_id = event.chat_id
        duplicates_map = self._get_cached_scan_result(chat_id)
        if duplicates_map is None:
            return False, "请先进行扫描"
        if mode == "keep":
            self._clear_scan_result(chat_id)
            session = self._get_user_session(chat_id)
            session.pop('selected_signatures', None)
            session.pop('sig_mapping', None)
            return True, "已保留重复项"
        if not duplicates_map:
            return True, "没有发现重复项"
        msg_ids_to_delete = []
        if mode == "all":
            for ids in duplicates_map.values():
                msg_ids_to_delete.extend(ids)
        else:
            selected = self._get_user_session(chat_id).get('selected_signatures', [])
            for sig in selected:
                if sig in duplicates_map:
                    msg_ids_to_delete.extend(duplicates_map[sig])
        if not msg_ids_to_delete:
            return False, "未发现或未选择任何重复项"
        session = self._get_user_session(chat_id)
        session['delete_task'] = {
            "deleted": 0, "total": len(msg_ids_to_delete),
            "status": "running", "cancel_event": asyncio.Event()
        }
        task_future = asyncio.create_task(self._execute_batch_delete(chat_id, msg_ids_to_delete))
        session['delete_task']['future'] = task_future
        return True, "已启动后台删除任务"

    async def _execute_batch_delete(self, chat_id, msg_ids):
        client = container.user_client
        session = self._get_user_session(chat_id)
        task = session.get('delete_task')
        deleted = 0
        batch_size = 100
        try:
            for i in range(0, len(msg_ids), batch_size):
                if task and task.get('cancel_event') and task['cancel_event'].is_set():
                    task['status'] = "cancelled"
                    break
                batch = msg_ids[i:i+batch_size]
                try:
                    await client.delete_messages(chat_id, batch)
                    deleted += len(batch)
                    if task:
                        task['deleted'] = deleted
                    await asyncio.sleep(1.0)
                except Exception as e:
                    logger.error(f"删除批次 {i} 失败: {e}")
                    await asyncio.sleep(5.0)
            if task and task.get('status') == "running":
                task['status'] = "completed"
            self._clear_scan_result(chat_id)
        except Exception as e:
            logger.error(f"批量删除任务崩溃: {e}", exc_info=True)
            if task:
                task['status'] = "failed"

    async def get_delete_progress(self, chat_id):
        task = self._get_user_session(chat_id).get('delete_task')
        if not task:
            return {"deleted": 0, "total": 0, "status": "idle"}
        return {"deleted": task.get("deleted", 0), "total": task.get("total", 0), "status": task.get("status", "unknown")}

    def _signature_to_display_name(self, sig):
        if ":" in str(sig):
            parts = str(sig).split(":", 1)
            return f"[{parts[0]}] {parts[1][:15]}..."
        return str(sig)[:20]

    async def stop_delete_task(self, chat_id):
        task = self._get_user_session(chat_id).get('delete_task')
        if task and task.get('cancel_event'):
            task['cancel_event'].set()
            task['status'] = "cancelled"
            return True
        return False

    async def pause_delete_task(self, chat_id):
        task = self._get_user_session(chat_id).get('delete_task')
        if task and task.get('cancel_event'):
            task['cancel_event'].set()
            task['status'] = "paused"
            return True
        return False

    async def preview_session_messages_by_filter(self, event, limit=10):
        chat_id = event.chat_id
        time_config = self.get_time_range(chat_id)
        begin_date, end_date, _, _ = parse_time_range_to_dates(time_config)
        client = container.user_client
        samples = []
        count = 0
        try:
            async for message in client.iter_messages(chat_id, offset_date=begin_date, reverse=True):
                if end_date and message.date > end_date.replace(tzinfo=None):
                    break
                count += 1
                if len(samples) < limit:
                    samples.append(message)
            return count, samples
        except Exception as e:
            logger.error(f"Preview session messages failed: {e}")
            return 0, []

    async def delete_session_messages_by_filter(self, event):
        chat_id = event.chat_id
        time_config = self.get_time_range(chat_id)
        begin_date, end_date, _, _ = parse_time_range_to_dates(time_config)
        client = container.user_client
        msg_ids = []
        try:
            async for message in client.iter_messages(chat_id, offset_date=begin_date, reverse=True):
                if end_date and message.date > end_date.replace(tzinfo=None):
                    break
                msg_ids.append(message.id)
            if not msg_ids:
                return True, "没有匹配的消息"
            session = self._get_user_session(chat_id)
            session['delete_task'] = {
                "deleted": 0, "total": len(msg_ids),
                "status": "running", "cancel_event": asyncio.Event()
            }
            task_future = asyncio.create_task(self._execute_batch_delete(chat_id, msg_ids))
            session['delete_task']['future'] = task_future
            return True, "已启动后台清理任务"
        except Exception as e:
            logger.error(f"Batch delete failed: {e}")
            return False, str(e)

    async def get_selection_state(self, chat_id):
        return self._get_user_session(chat_id).get('selected_signatures', [])

    async def toggle_select_signature(self, chat_id, sig_id):
        session = self._get_user_session(chat_id)
        if 'selected_signatures' not in session:
            session['selected_signatures'] = []
        sig_mapping = session.get('sig_mapping', {})
        real_sig = sig_mapping.get(sig_id, sig_id)
        if real_sig in session['selected_signatures']:
            session['selected_signatures'].remove(real_sig)
        else:
            session['selected_signatures'].append(real_sig)
        return True
