"""
会话管理功能模块
负责维护用户会话状态、历史任务进度及时间范围设置
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from telethon import events
from core.container import container
from core.helpers.tombstone import tombstone
from core.helpers.time_range import format_time_range_display, parse_time_range_to_dates
from models.models import TaskQueue

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        # user_sessions[user_id] = {
        #   'selected_rule_id': int,
        #   'time_range': dict,
        #   'delay': int,
        #   'history_task': {
        #       'status': str, 'total': int, 'done': int, ...
        #       'cancel_event': asyncio.Event()
        #   }
        # }
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.current_scan_results: Dict[str, Any] = {}
        
        # [Scheme 7 Fix] 注册到墓碑，实现重启恢复
        tombstone.register(
            "session_manager", self._get_state_dump, self._restore_state_dump
        )
        self._initialized = True
        logger.info("SessionManager initialized with tombstone support")

    def _get_state_dump(self):
        # 序列化状态，忽略不可序列化对象 (如 Event)
        serializable_sessions = {}
        for uid, session in self.user_sessions.items():
            s = session.copy()
            if 'history_task' in s:
                # 仅保留任务状态数据，丢弃运行时对象
                task_info = s['history_task'].copy()
                task_info.pop('cancel_event', None)
                task_info.pop('future', None)
                s['history_task'] = task_info
            serializable_sessions[uid] = s
            
        return {
            "user_sessions": serializable_sessions,
            "current_scan_results": self.current_scan_results,
        }

    def _restore_state_dump(self, dump):
        if dump:
            self.user_sessions = dump.get("user_sessions", {})
            # 转换 key 为 int (JSON key 总是 str)
            self.user_sessions = {int(k): v for k, v in self.user_sessions.items()}
            self.current_scan_results = dump.get("current_scan_results", {})
            logger.info(
                f"🔥 SessionManager 恢复了 {len(self.user_sessions)} 个用户会话"
            )

    def _get_user_session(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        return self.user_sessions[user_id]

    async def get_selected_rule(self, user_id: int) -> Optional[int]:
        """获取选中的规则ID"""
        return self._get_user_session(user_id).get('selected_rule_id')

    async def set_selected_rule(self, user_id: int, rule_id: int):
        """设置选中的规则ID"""
        self._get_user_session(user_id)['selected_rule_id'] = rule_id

    def get_time_range(self, user_id: int) -> Dict[str, int]:
        """获取时间范围配置"""
        return self._get_user_session(user_id).get('time_range', {})

    def set_time_range(self, user_id: int, time_range: Dict[str, int]):
        """设置时间范围配置"""
        self._get_user_session(user_id)['time_range'] = time_range

    def get_delay_setting(self, user_id: int) -> int:
        """获取延迟设置"""
        return self._get_user_session(user_id).get('delay', 0)

    def set_delay_setting(self, user_id: int, delay: int):
        """设置延迟设置"""
        self._get_user_session(user_id)['delay'] = delay

    async def get_history_progress(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取历史任务进度"""
        session = self._get_user_session(user_id)
        return session.get('history_task')

    async def start_history_task(self, user_id: int, rule_id: Optional[int] = None, time_config: Optional[Dict] = None) -> Dict[str, Any]:
        """启动历史任务"""
        session = self._get_user_session(user_id)
        
        # 如果有正在运行的任务，先阻止
        current_task = session.get('history_task')
        if current_task and current_task.get('status') == 'running':
             return {'success': False, 'message': '已有正在运行的任务'}

        # 获取配置
        rule_id = rule_id or session.get('selected_rule_id')
        if not rule_id:
            return {'success': False, 'message': '未选择转发规则'}
            
        time_config = time_config or session.get('time_range', {})
        
        # 初始化任务状态
        cancel_event = asyncio.Event()
        task_info = {
            'status': 'running',
            'start_time': datetime.now().isoformat(),
            'total': 0,
            'done': 0,
            'forwarded': 0,
            'filtered': 0,
            'failed': 0,
            'cancel_event': cancel_event,
            'current_message_id': 0
        }
        session['history_task'] = task_info
        
        # 启动后台任务
        task_future = asyncio.create_task(
            self._run_history_task(user_id, rule_id, time_config, cancel_event)
        )
        task_info['future'] = task_future
        
        return {'success': True, 'message': '历史消息转发任务已启动'}

    async def stop_history_task(self, user_id: int) -> bool:
        """停止历史任务"""
        session = self._get_user_session(user_id)
        task_info = session.get('history_task')
        
        if task_info and task_info.get('status') == 'running':
            if 'cancel_event' in task_info:
                task_info['cancel_event'].set()
            task_info['status'] = 'cancelled'
            return True
        return False

    async def _run_history_task(self, user_id: int, rule_id: int, time_config: Dict, cancel_event: asyncio.Event):
        """历史任务执行循环 - 增强版"""
        from utils.history import (
            HistoryTaskProgress,
            BackpressureController,
            ErrorHandler,
            MediaFilter,
        )
        
        session = self._get_user_session(user_id)
        task_info = session.get('history_task')
        
        # 初始化工具类
        progress = HistoryTaskProgress()
        backpressure = BackpressureController(
            max_pending=1000,
            check_interval=100,
            pause_threshold=0.8,
            resume_threshold=0.5
        )
        error_handler = ErrorHandler(max_retries=3, base_delay=1.0)
        
        # 获取全局媒体设置
        try:
            from handlers.button.forward_management import forward_manager
            media_settings = await forward_manager.get_global_media_settings()
        except Exception as e:
            logger.warning(f"获取媒体设置失败，使用默认设置: {e}")
            media_settings = None
        
        media_filter = MediaFilter(media_settings)
        
        try:
            from models.models import ForwardRule, Chat
            from sqlalchemy import select
            
            # 1. 获取规则详情
            async with container.db.session() as db_session:
                stmt = select(ForwardRule).where(ForwardRule.id == rule_id)
                rule = (await db_session.execute(stmt)).scalar_one_or_none()
                if not rule:
                    raise ValueError(f"Rule {rule_id} not found")
                
                # 获取源聊天
                source_chat = await db_session.get(Chat, rule.source_chat_id)
                if not source_chat:
                    raise ValueError("Source chat not found")
                
                source_chat_id = int(source_chat.telegram_chat_id)
                target_chat_id = int(rule.target_chat.telegram_chat_id)
            
            # 2. 解析时间范围
            begin_date, end_date, start_s, end_s = parse_time_range_to_dates(time_config)
            
            # 3. 估算消息总数
            client = container.user_client
            try:
                estimated_total = await self._estimate_message_count(
                    client, source_chat_id, begin_date, end_date
                )
                progress.total = estimated_total
                task_info['total'] = estimated_total
                logger.info(f"📊 估算消息总数: {estimated_total}")
            except Exception as e:
                logger.warning(f"消息总数估算失败: {e}")
                progress.total = 0
                task_info['total'] = 0
            
            # 4. 开始迭代消息
            logger.info(
                f"🚀 开始历史消息处理: "
                f"user_id={user_id}, rule_id={rule_id}, "
                f"source={source_chat_id}, target={target_chat_id}"
            )
            
            async for message in client.iter_messages(
                source_chat_id, reverse=True, offset_date=begin_date
            ):
                # 检查取消事件
                if cancel_event.is_set():
                    logger.info(f"⏸️ 历史任务已取消: user_id={user_id}")
                    progress.status = "cancelled"
                    break
                
                # 检查结束时间
                if end_date and message.date > end_date.replace(tzinfo=timezone.utc):
                    logger.info(f"✅ 已达到结束时间: {end_date}")
                    break
                
                # 更新当前消息ID
                progress.current_message_id = message.id
                task_info['current_message_id'] = message.id
                
                # 媒体筛选
                should_process, filter_reason = await media_filter.should_process_message(message)
                if not should_process:
                    progress.increment('filtered')
                    progress.increment('done')
                    task_info['filtered'] = progress.filtered
                    task_info['done'] = progress.done
                    logger.debug(f"⏭️ 消息 {message.id} 被过滤: {filter_reason}")
                    continue
                
                # 推送到处理队列
                payload = {
                    "chat_id": source_chat_id,
                    "message_id": message.id,
                    "rule_id": rule_id,
                    "is_history": True,
                    "target_chat_id": target_chat_id
                }
                
                # 使用错误处理器推送任务
                context = {
                    'user_id': user_id,
                    'rule_id': rule_id,
                    'message_id': message.id
                }
                
                success, result = await error_handler.retry_with_backoff(
                    container.task_repo.push,
                    "process_message",
                    payload,
                    priority=5,
                    context=context
                )
                
                if success:
                    progress.increment('forwarded')
                    task_info['forwarded'] = progress.forwarded
                else:
                    progress.increment('failed')
                    task_info['failed'] = progress.failed
                    logger.error(f"❌ 消息 {message.id} 推送失败: {result}")
                
                # 更新进度
                progress.increment('done')
                task_info['done'] = progress.done
                
                # 背压控制
                should_continue = await backpressure.check_and_wait(
                    container.task_repo,
                    progress.done,
                    cancel_event
                )
                
                if not should_continue:
                    logger.info(f"⏸️ 历史任务被取消: user_id={user_id}")
                    progress.status = "cancelled"
                    break
                
                # 定期更新任务信息
                if progress.done % 50 == 0:
                    task_info.update(progress.to_dict())
                    logger.info(
                        f"📈 进度更新: {progress.done}/{progress.total} "
                        f"({progress.get_percentage():.1f}%) "
                        f"转发={progress.forwarded} 过滤={progress.filtered} "
                        f"失败={progress.failed}"
                    )
            
            # 任务完成
            if progress.status != "cancelled":
                progress.status = "completed"
            
            task_info.update(progress.to_dict())
            
            # 输出统计信息
            logger.info(
                f"✅ 历史任务完成: user_id={user_id}\n"
                f"  总计: {progress.total}\n"
                f"  处理: {progress.done}\n"
                f"  转发: {progress.forwarded}\n"
                f"  过滤: {progress.filtered}\n"
                f"  失败: {progress.failed}\n"
                f"  用时: {progress.get_elapsed_time()}\n"
                f"  速度: {progress.get_processing_speed():.1f} 条/秒"
            )
            
            # 输出工具类统计
            logger.info(f"背压统计: {backpressure.get_statistics()}")
            logger.info(f"错误统计: {error_handler.get_statistics()}")
            logger.info(f"筛选统计: {media_filter.get_statistics()}")
            
        except Exception as e:
            logger.error(f"❌ 历史任务失败: user_id={user_id}, error={e}", exc_info=True)
            if task_info:
                task_info['status'] = 'failed'
                task_info['error'] = str(e)
            
            # 记录详细错误
            error_handler.log_error(
                e,
                context={
                    'user_id': user_id,
                    'rule_id': rule_id,
                    'progress': progress.to_dict()
                }
            )
    
    async def _estimate_message_count(
        self, client, chat_id: int, begin_date=None, end_date=None
    ) -> int:
        """估算消息总数"""
        try:
            # 获取第一条和最后一条消息
            first_msgs = await client.get_messages(chat_id, limit=1, reverse=True)
            last_msgs = await client.get_messages(chat_id, limit=1)
            
            if not first_msgs or not last_msgs:
                return 0
            
            first_msg = first_msgs[0]
            last_msg = last_msgs[0]
            
            # 如果没有时间范围，直接返回ID差值
            if not begin_date and not end_date:
                return max(0, last_msg.id - first_msg.id)
            
            # 有时间范围时，使用简化估算
            # TODO: 实现更精确的二分查找估算
            total_range = last_msg.id - first_msg.id
            
            # 粗略估算: 假设消息均匀分布
            if begin_date or end_date:
                # 简化处理: 返回总数的一半作为估算
                return total_range // 2
            
            return total_range
            
        except Exception as e:
            logger.warning(f"估算消息总数失败: {e}")
            return 0
    
    # --- 兼容接口与其他辅助方法 ---

    def get_time_picker_context(self, chat_id):
        """获取时间选择器上下文"""
        return self._get_user_session(chat_id).get('picker_context', 'session')

    def set_time_picker_context(self, chat_id, context):
        """设置时间选择器上下文"""
        self._get_user_session(chat_id)['picker_context'] = context

    async def get_time_range_display(self, chat_id):
        """获取时间范围显示"""
        tr = self.get_time_range(chat_id)
        return format_time_range_display(tr)

    async def get_chat_message_date_range(self, chat_id):
        """获取聊天消息日期范围 (需要实际获取消息)"""
        # 这是一个耗时操作，建议缓存或简化
        try:
            client = container.user_client
            # 获取第一条和最后一条
            messages = await client.get_messages(chat_id, limit=1, reverse=True)
            first_date = messages[0].date if messages else None
            
            messages = await client.get_messages(chat_id, limit=1)
            last_date = messages[0].date if messages else None
            
            return first_date, last_date
        except Exception:
            return None, None

    async def scan_duplicate_messages(self, event, progress_callback=None):
        """扫描重复消息 (实现对齐)"""
        try:
            chat_id = event.chat_id
            # TODO: 实现完整扫描逻辑
            # 目前仅返回空状态，待 SmartDedup 集成完善
            # Current placeholder: Return empty dict to indicate no duplicates found yet (checks fail gracefully)
            # preventing "object of type 'int' has no len()" error in new_menu_system
            self.current_scan_results[chat_id] = {}
            return self.current_scan_results[chat_id]
        except Exception as e:
            logger.error(f"Scan duplicates failed: {e}")
            return {}

    async def set_time_component(self, chat_id, side, field, value):
        tr = self.get_time_range(chat_id)
        key = f"{side}_{field}"
        tr[key] = int(value)
        self.set_time_range(chat_id, tr)

    async def set_time_field(self, chat_id, side, field, value):
        """设置时间字段 (set_time_component 的别名)"""
        await self.set_time_component(chat_id, side, field, value)

    # 占位方法兼容
    async def delete_duplicate_messages(self, event, mode="all"):
        return True, "功能开发中"
    
    async def get_delete_progress(self, chat_id):
        return {"deleted": 0, "total": 0}

    async def preview_session_messages_by_filter(self, event):
        return 0, []

    async def save_time_range_settings(self, chat_id):
        return True

    async def delete_session_messages_by_filter(self, event):
        return True, "功能开发中"

    async def pause_delete_task(self, chat_id):
        return True

    async def stop_delete_task(self, chat_id):
        return True

    async def preview_history_messages(self, event, sample=10, collect_full=True, max_collect=800):
        return 0, []

    async def count_history_in_range(self, event):
        return 0, 0

    async def diagnose_history_filter_issues(self, event):
        return "无问题"

    def get_last_dry_run_debug(self, chat_id):
        return None

    async def get_history_delay(self, chat_id):
        return self.get_delay_setting(chat_id)

    def _signature_to_display_name(self, sig):
        return str(sig)

    def is_auto_refresh_enabled(self, chat_id):
        return False

    async def set_auto_refresh(self, chat_id, enabled, message_id):
        pass

    async def get_selection_state(self, chat_id):
        return {}

    async def toggle_select_signature(self, chat_id, signature):
        pass


# 创建全局会话管理器实例
session_manager = SessionManager()
