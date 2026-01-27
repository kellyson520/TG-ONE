"""
会话管理服务层
负责维护用户会话状态、历史任务进度及时间范围设置
并提供历史消息任务的执行引擎
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from core.container import container
from core.helpers.tombstone import tombstone
from core.helpers.time_range import format_time_range_display, parse_time_range_to_dates
from models.models import TaskQueue
from services.forward_settings_service import forward_settings_service

logger = logging.getLogger(__name__)


class SessionService:
    """会话管理业务逻辑服务 (原 SessionManager)"""

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
        #   },
        #   'picker_context': str (optional)
        # }
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.current_scan_results: Dict[str, Any] = {}
        
        # 注册到墓碑，实现重启恢复
        tombstone.register(
            "session_service", self._get_state_dump, self._restore_state_dump
        )
        self._initialized = True
        logger.info("SessionService initialized with tombstone support")

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
                f"🔥 SessionService 恢复了 {len(self.user_sessions)} 个用户会话"
            )

    def _get_user_session(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        return self.user_sessions[user_id]

    async def get_selected_rule(self, user_id: int) -> Dict[str, Any]:
        """获取当前选中的规则详情 (API 兼容格式)"""
        try:
            rule_id = self._get_user_session(user_id).get('selected_rule_id')
            
            if rule_id is None:
                return {
                    'has_selection': False,
                    'rule': None,
                    'message': '请先选择一个转发规则'
                }
            
            # 获取规则详情
            from services.rule_management_service import rule_management_service
            rule_detail = await rule_management_service.get_rule_detail(rule_id)
            
            if not rule_detail['success']:
                return {
                    'has_selection': False,
                    'rule': None,
                    'error': f'规则 {rule_id} 不存在或已被删除'
                }
            
            # 统一为渲染器/调用方期望的结构
            try:
                rule_obj = {
                    'id': rule_id,
                    'source_chat': {
                        'title': rule_detail.get('source_chat') or 'Unknown',
                        'telegram_chat_id': None,
                    },
                    'target_chat': {
                        'title': rule_detail.get('target_chat') or 'Unknown',
                        'telegram_chat_id': None,
                    },
                    'settings': {
                        'enabled': bool(rule_detail.get('enabled', True)),
                        'enable_dedup': bool(rule_detail.get('enable_dedup', False)),
                    },
                    'keywords': [],
                    'replace_rules': [],
                }
            except Exception:
                rule_obj = {'id': rule_id, 'source_chat': {'title': 'Unknown'}, 'target_chat': {'title': 'Unknown'}, 'settings': {}}
            return {
                'has_selection': True,
                'rule': rule_obj,
                'rule_id': rule_id
            }
            
        except Exception as e:
            logger.error(f"获取选中规则失败: {e}")
            return {'has_selection': False, 'rule': None, 'error': str(e)}

    async def set_selected_rule(self, user_id: int, rule_id: int) -> Dict[str, Any]:
        """设置选中的规则"""
        try:
            from services.rule_management_service import rule_management_service
            rule_detail = await rule_management_service.get_rule_detail(rule_id)
            
            if not rule_detail['success']:
                return {'success': False, 'error': f'规则 {rule_id} 不存在'}
            
            self._get_user_session(user_id)['selected_rule_id'] = rule_id
            
            # 构建返回部分，不需要重复代码，保持简单返回即可，或按需返回
            # 为保持兼容性，构建 rule_obj
            try:
                rule_obj = {
                    'id': rule_id,
                    'source_chat': {'title': rule_detail.get('source_chat') or 'Unknown'},
                    'target_chat': {'title': rule_detail.get('target_chat') or 'Unknown'},
                }
            except Exception:
                rule_obj = {}

            return {
                'success': True,
                'rule_id': rule_id,
                'rule': rule_obj,
                'message': f'已选择规则 {rule_id}'
            }
        except Exception as e:
            logger.error(f"设置选中规则失败: {e}")
            return {'success': False, 'error': str(e)}

    def get_time_range(self, user_id: int) -> Dict[str, int]:
        """获取时间范围原始配置"""
        return self._get_user_session(user_id).get('time_range', {})

    def set_time_range(self, user_id: int, time_range: Dict[str, int]):
        """设置时间范围原始配置"""
        self._get_user_session(user_id)['time_range'] = time_range

    async def get_time_range_config(self, user_id: int) -> Dict[str, Any]:
        """获取时间范围配置 (API 兼容格式)"""
        try:
            time_range = self.get_time_range(user_id)
            
            # 提供默认值
            if not time_range:
                time_range = {
                    'start_year': 0, 'start_month': 0, 'start_day': 0,
                    'start_hour': 0, 'start_minute': 0, 'start_second': 0,
                    'end_year': 0, 'end_month': 0, 'end_day': 0,
                    'end_hour': 0, 'end_minute': 0, 'end_second': 0
                }
            
            is_all_messages = all(time_range.get(key, 0) == 0 for key in time_range.keys())
            
            try:
                display_text = format_time_range_display(time_range)
            except Exception:
                display_text = "全部时间" if is_all_messages else "自定义"
                
            return {
                'success': True,
                'time_range': time_range,
                'is_all_messages': is_all_messages,
                'display_text': display_text
            }
        except Exception as e:
            logger.error(f"获取时间范围配置失败: {e}")
            return {'success': False, 'error': str(e)}

    async def update_time_range(self, user_id: int, **time_params) -> Dict[str, Any]:
        """更新时间范围"""
        try:
            current = self.get_time_range(user_id) or {}
            updated = {**current, **time_params}
            self.set_time_range(user_id, updated)
            return {'success': True, 'time_range': updated, 'message': '时间范围已更新'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_delay_settings(self, user_id: int) -> Dict[str, Any]:
        """获取延迟设置 (API 兼容格式)"""
        try:
            delay = self._get_user_session(user_id).get('delay', 0)
            return {
                'success': True,
                'delay_seconds': delay,
                'delay_text': self._format_delay_text(delay)
            }
        except Exception as e:
             return {'success': False, 'error': str(e), 'delay_seconds': 0}

    async def update_delay_setting(self, user_id: int, delay_seconds: int) -> Dict[str, Any]:
        """更新延迟设置"""
        try:
            if delay_seconds < 0 or delay_seconds > 3600:
                return {'success': False, 'error': '延迟时间必须在0-3600秒之间'}
            
            self._get_user_session(user_id)['delay'] = delay_seconds
            return {
                'success': True,
                'delay_seconds': delay_seconds,
                'delay_text': self._format_delay_text(delay_seconds),
                'message': f'延迟已设置为 {self._format_delay_text(delay_seconds)}'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _format_delay_text(self, delay: int) -> str:
        if delay == 0: return "无延迟"
        elif delay < 60: return f"{delay}秒"
        else: return f"{delay // 60}分{delay % 60}秒"

    async def get_history_task_status(self, user_id: int) -> Dict[str, Any]:
        """获取历史任务状态 (API 兼容格式)"""
        try:
            progress = await self.get_history_progress(user_id)
            
            if progress is None:
                return {
                    'has_task': False,
                    'status': None,
                    'progress': None,
                    'message': '当前没有运行的历史任务'
                }
            
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
        """获取历史任务进度原始数据"""
        session = self._get_user_session(user_id)
        return session.get('history_task')

    async def start_history_task(self, user_id: int, rule_id: Optional[int] = None, time_config: Optional[Dict] = None) -> Dict[str, Any]:
        """启动历史任务"""
        try:
            session = self._get_user_session(user_id)
            
            # 如果有正在运行的任务，先阻止
            current_task = session.get('history_task')
            if current_task and current_task.get('status') == 'running':
                return {'success': False, 'message': '已有正在运行的任务'}

            # 获取配置
            if rule_id is None:
                # 尝试从参数获取，或者从session中获取选中规则
                res = await self.get_selected_rule(user_id)
                if res['has_selection']:
                    rule_id = res['rule_id']
                else:
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
            
            return {'success': True, 'message': '历史消息转发任务已启动', 'task_id': f"hist_{user_id}"}
        except Exception as e:
            logger.error(f"启动历史任务失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def cancel_history_task(self, user_id: int) -> Dict[str, Any]:
        """取消历史任务"""
        result = await self.stop_history_task(user_id)
        return {
            'success': result,
            'message': '任务已取消' if result else '取消任务失败'
        }

    async def stop_history_task(self, user_id: int) -> bool:
        """停止历史任务 (Internal)"""
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
        from core.helpers.history import (
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
        
        # 获取全局媒体设置 (直接使用 ForwardSettingsService)
        try:
            media_settings = await forward_settings_service.get_global_media_settings()
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
            total_range = last_msg.id - first_msg.id
            
            # 粗略估算: 假设消息均匀分布
            if begin_date or end_date:
                # 简化处理: 返回总数的一半作为估算
                return total_range // 2
            
            return total_range
            
        except Exception as e:
            logger.warning(f"估算消息总数失败: {e}")
            return 0

    def _calculate_estimated_time(self, progress: Dict[str, Any]) -> Optional[str]:
        """计算预估剩余时间"""
        try:
            total = progress.get('total', 0)
            done = progress.get('done', 0)
            start_time = progress.get('start_time')
            
            if not start_time or done <= 0 or total <= done:
                return None
            
            # 计算平均处理速度
            elapsed = (datetime.now() - datetime.fromisoformat(start_time)).total_seconds()
            speed = done / elapsed  # 条/秒
            
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

    # --- 辅助方法与上下文管理 ---

    async def update_user_state(self, user_id: int, chat_id: int, state: str, rule_id: int, extra: Dict[str, Any] = None):
        """更新用户会话状态"""
        try:
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {}
            
            session_data = {
                "state": state,
                "rule_id": rule_id,
                "message": {"rule_id": rule_id}
            }
            if extra:
                session_data.update(extra)
                
            if 'chat_states' not in self.user_sessions[user_id]:
                self.user_sessions[user_id]['chat_states'] = {}
            
            self.user_sessions[user_id]['chat_states'][chat_id] = session_data
            return True
        except Exception as e:
            logger.error(f"更新用户会话状态失败: {e}")
            return False

    async def get_available_rules(self, user_id: int) -> Dict[str, Any]:
        """获取可用的转发规则"""
        try:
            from models.models import ForwardRule
            from sqlalchemy.orm import selectinload
            
            async with container.db.session() as session:
                # 预加载关联的聊天和关键字
                stmt = select(ForwardRule).options(
                    selectinload(ForwardRule.source_chat),
                    selectinload(ForwardRule.target_chat),
                    selectinload(ForwardRule.keywords)
                ).filter_by(enable_rule=True)
                
                result = await session.execute(stmt)
                rules = result.scalars().all()
                
                rules_data = []
                for rule in rules:
                    try:
                        source_chat = rule.source_chat
                        target_chat = rule.target_chat
                        
                        if source_chat and target_chat:
                            rules_data.append({
                                'id': rule.id,
                                'source_title': getattr(source_chat, 'name', None) or f"Chat {getattr(source_chat, 'telegram_chat_id', '')}",
                                'target_title': getattr(target_chat, 'name', None) or f"Chat {getattr(target_chat, 'telegram_chat_id', '')}",
                                'source_chat_id': getattr(source_chat, 'telegram_chat_id', None),
                                'target_chat_id': getattr(target_chat, 'telegram_chat_id', None),
                                'keywords_count': len(getattr(rule, 'keywords', [])),
                                'enable_dedup': getattr(rule, 'enable_dedup', False)
                            })
                    except Exception as e:
                        logger.warning(f"处理规则 {rule.id} 时出错: {e}")
                        continue
                
                return {
                    'success': True,
                    'rules': rules_data,
                    'total_count': len(rules_data)
                }
        except Exception as e:
            logger.error(f"获取可用规则失败: {e}")
            return {'success': False, 'error': str(e), 'rules': [], 'total_count': 0}

    # --- Time Picker Context Helpers ---

    def get_time_picker_context(self, chat_id):
        return self._get_user_session(chat_id).get('picker_context', 'session')

    def set_time_picker_context(self, chat_id, context):
        self._get_user_session(chat_id)['picker_context'] = context

    async def get_time_range_display(self, chat_id):
        tr = self.get_time_range(chat_id)
        return format_time_range_display(tr)

    async def set_time_component(self, chat_id, side, field, value):
        tr = self.get_time_range(chat_id)
        key = f"{side}_{field}"
        tr[key] = int(value)
        self.set_time_range(chat_id, tr)

    async def set_time_field(self, chat_id, side, field, value):
        await self.set_time_component(chat_id, side, field, value)

    # --- 兼容性方法 (Placeholder/Future) ---
    async def scan_duplicate_messages(self, event, progress_callback=None):
        chat_id = event.chat_id
        self.current_scan_results[chat_id] = {}
        return self.current_scan_results[chat_id]

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
        return self._get_user_session(chat_id).get('delay', 0)

    def is_auto_refresh_enabled(self, chat_id):
        return False

    async def set_auto_refresh(self, chat_id, enabled, message_id):
        pass

    async def get_selection_state(self, chat_id):
        return {}
    
    async def toggle_select_signature(self, chat_id, signature):
        pass


system_session_service = SessionService()
# Alias for backward compatibility (external modules might import session_service)
session_service = system_session_service
# Alias for session_manager transition
session_manager = system_session_service
