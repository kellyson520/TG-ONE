import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core.container import container
from core.helpers.time_range import parse_time_range_to_dates
from services.forward_settings_service import forward_settings_service

logger = logging.getLogger(__name__)


class SessionHistoryMixin:
    """历史任务管理相关方法"""

    async def get_history_task_status(self, user_id: int) -> Dict[str, Any]:
        try:
            progress = await self.get_history_progress(user_id)
            if progress is None:
                return {'has_task': False, 'status': None, 'progress': None, 'message': '当前没有运行的历史任务'}
            return {
                'has_task': True,
                'status': progress.get('status', 'unknown'),
                'progress': {
                    'total': progress.get('total', 0),
                    'done': progress.get('done', 0),
                    'forwarded': progress.get('forwarded', 0),
                    'filtered': progress.get('filtered', 0),
                    'failed': progress.get('failed', 0),
                    'percentage': (progress.get('done', 0) / max(progress.get('total', 1), 1)) * 100
                },
                'start_time': progress.get('start_time'),
                'estimated_remaining': self._calculate_estimated_time(progress)
            }
        except Exception as e:
            return {'has_task': False, 'status': 'error', 'error': str(e)}

    async def get_history_progress(self, user_id: int) -> Optional[Dict[str, Any]]:
        session = self._get_user_session(user_id)
        return session.get('history_task')

    async def start_history_task(self, user_id: int, rule_id: Optional[int] = None, time_config: Optional[Dict] = None, dry_run: bool = False) -> Dict[str, Any]:
        try:
            session = self._get_user_session(user_id)
            current_task = session.get('history_task')
            if current_task and current_task.get('status') == 'running':
                return {'success': False, 'message': '已有正在运行的任务'}
            if rule_id is None:
                res = await self.get_selected_rule(user_id)
                if res['has_selection']:
                    rule_id = res['rule_id']
                else:
                    return {'success': False, 'message': '未选择转发规则'}
            time_config = time_config or session.get('time_range', {})
            cancel_event = asyncio.Event()
            task_info = {
                'status': 'running', 'mode': 'dry_run' if dry_run else 'normal',
                'start_time': datetime.now().isoformat(),
                'total': 0, 'done': 0, 'forwarded': 0, 'filtered': 0, 'failed': 0,
                'cancel_event': cancel_event, 'current_message_id': 0
            }
            session['history_task'] = task_info
            task_future = asyncio.create_task(
                self._run_history_task(user_id, rule_id, time_config, cancel_event, dry_run)
            )
            task_info['future'] = task_future
            return {'success': True, 'message': '历史消息转发任务已启动', 'task_id': f"hist_{user_id}"}
        except Exception as e:
            logger.error(f"启动历史任务失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def cancel_history_task(self, user_id: int) -> Dict[str, Any]:
        result = await self.stop_history_task(user_id)
        return {'success': result, 'message': '任务已取消' if result else '取消任务失败'}

    async def stop_history_task(self, user_id: int) -> bool:
        session = self._get_user_session(user_id)
        task_info = session.get('history_task')
        if task_info and task_info.get('status') == 'running':
            if 'cancel_event' in task_info:
                task_info['cancel_event'].set()
            task_info['status'] = 'cancelled'
            return True
        return False

    async def _run_history_task(self, user_id: int, rule_id: int, time_config: Dict, cancel_event: asyncio.Event, dry_run: bool = False):
        from core.helpers.history import (
            HistoryTaskProgress, BackpressureController, ErrorHandler, MediaFilter,
        )
        session = self._get_user_session(user_id)
        task_info = session.get('history_task')
        progress = HistoryTaskProgress()
        backpressure = BackpressureController(max_pending=1000, check_interval=100, pause_threshold=0.8, resume_threshold=0.5)
        error_handler = ErrorHandler(max_retries=3, base_delay=1.0)
        try:
            media_settings = await forward_settings_service.get_global_media_settings()
        except Exception as e:
            logger.warning(f"获取媒体设置失败，使用默认设置: {e}")
            media_settings = None
        media_filter = MediaFilter(media_settings)
        try:
            from core.config import settings
            runtime_limit = int(settings.HISTORY_MESSAGE_LIMIT or 0)
            stored_limit = int((media_settings or {}).get("HISTORY_MESSAGE_LIMIT") or 0)
            message_limit = runtime_limit or stored_limit
        except Exception:
            message_limit = 0
        try:
            rule = await container.rule_repo.get_by_id(rule_id)
            if not rule:
                raise ValueError(f"Rule {rule_id} not found")
            if not rule.source_chat:
                raise ValueError("Source chat not found")
            if not rule.target_chat:
                raise ValueError("Target chat not found")
            source_chat_id = int(rule.source_chat.telegram_chat_id)
            target_chat_id = int(rule.target_chat.telegram_chat_id)
            begin_date, end_date, start_s, end_s = parse_time_range_to_dates(time_config)
            client = container.user_client
            try:
                estimated_total = await self._estimate_message_count(client, source_chat_id, begin_date, end_date)
                if message_limit > 0 and estimated_total > 0:
                    estimated_total = min(estimated_total, message_limit)
                progress.total = estimated_total
                task_info['total'] = estimated_total
                logger.info(f"📊 估算消息总数: {estimated_total}")
            except Exception as e:
                logger.warning(f"消息总数估算失败: {e}")
                progress.total = 0
                task_info['total'] = 0
            logger.info(f"🚀 开始历史消息处理: user_id={user_id}, rule_id={rule_id}, source={source_chat_id}, target={target_chat_id}")
            async for message in client.iter_messages(source_chat_id, reverse=True, offset_date=begin_date, limit=message_limit or None):
                if message_limit > 0 and progress.done >= message_limit:
                    logger.info(f"✅ 已达到历史消息数量限制: {message_limit}")
                    break
                if cancel_event.is_set():
                    logger.info(f"⏸️ 历史任务已取消: user_id={user_id}")
                    progress.status = "cancelled"
                    break
                if end_date and message.date > end_date.replace(tzinfo=timezone.utc):
                    logger.info(f"✅ 已达到结束时间: {end_date}")
                    break
                progress.current_message_id = message.id
                task_info['current_message_id'] = message.id
                should_process, filter_reason = await media_filter.should_process_message(message)
                if not should_process:
                    progress.increment('filtered')
                    progress.increment('done')
                    task_info['filtered'] = progress.filtered
                    task_info['done'] = progress.done
                    logger.debug(f"⏭️ 消息 {message.id} 被过滤: {filter_reason}")
                    continue
                if dry_run:
                    progress.increment('forwarded')
                    progress.increment('done')
                    task_info['forwarded'] = progress.forwarded
                    task_info['done'] = progress.done
                    if progress.done % 50 == 0:
                        task_info.update(progress.to_dict())
                        should_continue = await backpressure.check_and_wait(container.task_repo, progress.done, cancel_event)
                        if not should_continue:
                            progress.status = "cancelled"
                            break
                        await asyncio.sleep(0.01)
                    continue
                payload = {"chat_id": source_chat_id, "message_id": message.id, "rule_id": rule_id, "is_history": True, "target_chat_id": target_chat_id}
                context = {'user_id': user_id, 'rule_id': rule_id, 'message_id': message.id}
                success, result = await error_handler.retry_with_backoff(container.task_repo.push, "process_message", payload, priority=5, context=context)
                if success:
                    progress.increment('forwarded')
                    task_info['forwarded'] = progress.forwarded
                else:
                    progress.increment('failed')
                    task_info['failed'] = progress.failed
                    logger.error(f"❌ 消息 {message.id} 推送失败: {result}")
                progress.increment('done')
                task_info['done'] = progress.done
                should_continue = await backpressure.check_and_wait(container.task_repo, progress.done, cancel_event)
                if not should_continue:
                    logger.info(f"⏸️ 历史任务被取消: user_id={user_id}")
                    progress.status = "cancelled"
                    break
                if progress.done % 50 == 0:
                    task_info.update(progress.to_dict())
                    logger.info(f"📈 进度更新: {progress.done}/{progress.total} ({progress.get_percentage():.1f}%) 转发={progress.forwarded} 过滤={progress.filtered} 失败={progress.failed}")
            if progress.status != "cancelled":
                progress.status = "completed"
            task_info.update(progress.to_dict())
            logger.info(f"✅ 历史任务完成: user_id={user_id}\n  总计: {progress.total}\n  处理: {progress.done}\n  转发: {progress.forwarded}\n  过滤: {progress.filtered}\n  失败: {progress.failed}\n  用时: {progress.get_elapsed_time()}\n  速度: {progress.get_processing_speed():.1f} 条/秒")
            logger.info(f"背压统计: {backpressure.get_statistics()}")
            logger.info(f"错误统计: {error_handler.get_statistics()}")
            logger.info(f"筛选统计: {media_filter.get_statistics()}")
        except Exception as e:
            logger.error(f"❌ 历史任务失败: user_id={user_id}, error={e}", exc_info=True)
            if task_info:
                task_info['status'] = 'failed'
                task_info['error'] = str(e)
            error_handler.log_error(e, context={'user_id': user_id, 'rule_id': rule_id, 'progress': progress.to_dict()})

    async def _estimate_message_count(self, client, chat_id: int, begin_date=None, end_date=None) -> int:
        try:
            first_msgs = await client.get_messages(chat_id, limit=1, reverse=True)
            last_msgs = await client.get_messages(chat_id, limit=1)
            if not first_msgs or not last_msgs:
                return 0
            total_first_id = first_msgs[0].id
            total_last_id = last_msgs[0].id
            if not begin_date and not end_date:
                return max(0, total_last_id - total_first_id)
            range_start_id = total_first_id
            range_end_id = total_last_id
            if begin_date:
                msgs = await client.get_messages(chat_id, limit=1, offset_date=begin_date, reverse=True)
                if msgs:
                    range_start_id = msgs[0].id
            if end_date:
                msgs = await client.get_messages(chat_id, limit=1, offset_date=end_date)
                if msgs:
                    range_end_id = msgs[0].id
            estimate = max(0, range_end_id - range_start_id)
            logger.info(f"📊 探测范围: ID {range_start_id} 到 {range_end_id}, 估算总数: {estimate}")
            return estimate
        except Exception as e:
            logger.warning(f"估算消息总数失败: {e}")
            return 0

    async def get_quick_stats(self, user_id: int) -> Dict[str, Any]:
        try:
            res = await self.get_selected_rule(user_id)
            if not res['has_selection']:
                return {'success': False, 'error': '未选择转发规则'}
            rule_id = res['rule_id']
            from core.container import container
            rule = await container.rule_repo.get_by_id(rule_id)
            if not rule or not rule.source_chat:
                return {'success': False, 'error': '规则源会话无效'}
            source_chat_id = int(rule.source_chat.telegram_chat_id)
            target_chat_title = rule.target_chat.name if rule.target_chat else 'Unknown'
            source_chat_title = rule.source_chat.name
            time_config = await self.get_time_range_config(user_id)
            time_range = time_config.get('time_range', {})
            begin_date, end_date, _, _ = parse_time_range_to_dates(time_range)
            client = container.user_client
            count = await self._estimate_message_count(client, source_chat_id, begin_date, end_date)
            try:
                from core.config import settings
                runtime_limit = int(settings.HISTORY_MESSAGE_LIMIT or 0)
                media_settings = await forward_settings_service.get_global_media_settings()
                stored_limit = int((media_settings or {}).get("HISTORY_MESSAGE_LIMIT") or 0)
                limit = runtime_limit or stored_limit
                if limit > 0 and count > 0:
                    count = min(count, limit)
            except Exception as e:
                logger.warning("History message limit lookup failed: user_id=%s rule_id=%s error=%s", user_id, rule_id, e)
            time_str = time_config.get('display_text', '全部时间')
            return {'success': True, 'count': count, 'time_range': time_str, 'source_title': source_chat_title, 'target_title': target_chat_title}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _calculate_estimated_time(self, progress: Dict[str, Any]) -> Optional[str]:
        try:
            total = progress.get('total', 0)
            done = progress.get('done', 0)
            start_time = progress.get('start_time')
            if not start_time or done <= 0 or total <= done:
                return None
            elapsed = (datetime.now() - datetime.fromisoformat(start_time)).total_seconds()
            speed = done / elapsed
            remaining_items = total - done
            remaining_seconds = remaining_items / speed
            if remaining_seconds < 60:
                return f"{remaining_seconds:.0f}秒"
            elif remaining_seconds < 3600:
                return f"{remaining_seconds / 60:.0f}分钟"
            else:
                return f"{remaining_seconds / 3600:.1f}小时"
        except Exception:
            return None

    async def get_history_delay(self, chat_id):
        return self._get_user_session(chat_id).get('delay', 0)

    async def preview_history_messages(self, event, _sample=10, _collect_full=True, _max_collect=800):
        from core.helpers.time_range import parse_time_range_to_dates
        chat_id = event.chat_id
        time_config = self.get_time_range(chat_id)
        begin_date, end_date, _, _ = parse_time_range_to_dates(time_config)
        client = container.user_client
        samples = []
        total = 0
        try:
            async for message in client.iter_messages(chat_id, offset_date=begin_date, limit=_max_collect, reverse=True):
                if end_date and message.date > end_date.replace(tzinfo=timezone.utc):
                    break
                total += 1
                if len(samples) < _sample:
                    samples.append(message)
            return total, samples
        except Exception as e:
            logger.error(f"预览历史消息失败: {e}")
            return 0, []

    async def count_history_in_range(self, event):
        return 0, 0

    async def diagnose_history_filter_issues(self, event):
        return "无问题"

    def get_last_dry_run_debug(self, chat_id):
        return None

    def is_auto_refresh_enabled(self, chat_id):
        return False

    async def set_auto_refresh(self, chat_id, enabled, message_id):
        pass
