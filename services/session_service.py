"""
会话管理服务层
负责维护用户会话状态、历史任务进度及时间范围设置
并提供历史消息任务的执行引擎
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from core.container import container
from core.helpers.tombstone import tombstone
from core.helpers.time_range import format_time_range_display, parse_time_range_to_dates
from services.forward_settings_service import forward_settings_service
from services.dedup.engine import smart_deduplicator

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
            # ✅ Fix: 强制使用字符串作为 Key，兼容 orjson
            serializable_sessions[str(uid)] = s
            
        # ✅ Fix: current_scan_results 也需要转换 key
        scan_results = {str(k): v for k, v in self.current_scan_results.items()}

        return {
            "user_sessions": serializable_sessions,
            "current_scan_results": scan_results,
        }

    def _restore_state_dump(self, dump):
        if dump:
            raw_sessions = dump.get("user_sessions", {})
            self.user_sessions = {}
            for uid_str, user_content in raw_sessions.items():
                try:
                    uid = int(uid_str)
                    processed_content = {}
                    for k, v in user_content.items():
                        # 如果 key 是数字字符串且不是保留字段名，则转换为 int (chat_id)
                        if k.isdigit() or (k.startswith('-') and k[1:].isdigit()):
                            processed_content[int(k)] = v
                        else:
                            processed_content[k] = v
                    self.user_sessions[uid] = processed_content
                except ValueError:
                    logger.warning(f"跳过无效的用户ID key: {uid_str}")
                
            # ✅ Fix: 恢复时将 Key 转回 int
            raw_scan_results = dump.get("current_scan_results", {})
            self.current_scan_results = {}
            for k, v in raw_scan_results.items():
                if k.isdigit() or (k.startswith('-') and k[1:].isdigit()):
                    self.current_scan_results[int(k)] = v
                else:
                    self.current_scan_results[k] = v

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

    async def start_history_task(self, user_id: int, rule_id: Optional[int] = None, time_config: Optional[Dict] = None, dry_run: bool = False) -> Dict[str, Any]:
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
                'mode': 'dry_run' if dry_run else 'normal',
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
                self._run_history_task(user_id, rule_id, time_config, cancel_event, dry_run)
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

    async def _run_history_task(self, user_id: int, rule_id: int, time_config: Dict, cancel_event: asyncio.Event, dry_run: bool = False):
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
            # 1. 获取规则详情
            rule = await container.rule_repo.get_by_id(rule_id)
            if not rule:
                raise ValueError(f"Rule {rule_id} not found")
            
            if not rule.source_chat:
                raise ValueError("Source chat not found")
                
            if not rule.target_chat:
                raise ValueError("Target chat not found")
            
            source_chat_id = int(rule.source_chat.telegram_chat_id)
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
                
                # Dry Run Logic
                if dry_run:
                    # 模拟成功处理
                    progress.increment('forwarded')
                    progress.increment('done')
                    task_info['forwarded'] = progress.forwarded
                    task_info['done'] = progress.done
                    
                    # 简单模拟背压，避免过快 (仅每50条check一次)
                    if progress.done % 50 == 0:
                        task_info.update(progress.to_dict())
                        should_continue = await backpressure.check_and_wait(
                            container.task_repo, # 这里可能需要 mock task_repo 或者 ignoring count
                            progress.done,
                            cancel_event
                        )
                        if not should_continue:
                            progress.status = "cancelled"
                            break
                        # 短暂 yield 释放 event loop
                        await asyncio.sleep(0.01)
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
        """估算消息总数 - 改进探测版"""
        try:
            # 获取会话中第一条和最后一条消息作为基准
            first_msgs = await client.get_messages(chat_id, limit=1, reverse=True)
            last_msgs = await client.get_messages(chat_id, limit=1)
            
            if not first_msgs or not last_msgs:
                return 0
            
            total_first_id = first_msgs[0].id
            total_last_id = last_msgs[0].id
            
            if not begin_date and not end_date:
                return max(0, total_last_id - total_first_id)
            
            # 使用 offset_date 探测范围端点
            range_start_id = total_first_id
            range_end_id = total_last_id
            
            if begin_date:
                # offset_date 获取 <= date 的消息，reverse=True 获取第一个 >= date 的消息
                msgs = await client.get_messages(chat_id, limit=1, offset_date=begin_date, reverse=True)
                if msgs:
                    range_start_id = msgs[0].id
                    
            if end_date:
                # offset_date 获取本就在 end_date 之前的消息
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
        """获取快速统计信息"""
        try:
             # 获取选中的规则
            res = await self.get_selected_rule(user_id)
            if not res['has_selection']:
                return {'success': False, 'error': '未选择转发规则'}
            
            rule_id = res['rule_id']
            # 直接查询数据库获取规则详情
            from core.container import container
            rule = await container.rule_repo.get_by_id(rule_id)
            if not rule or not rule.source_chat:
                return {'success': False, 'error': '规则源会话无效'}

            source_chat_id = int(rule.source_chat.telegram_chat_id)
            target_chat_title = rule.target_chat.name if rule.target_chat else 'Unknown'
            source_chat_title = rule.source_chat.name
            
            # 获取时间范围
            time_config = await self.get_time_range_config(user_id)
            time_range = time_config.get('time_range', {})
            begin_date, end_date, _, _ = parse_time_range_to_dates(time_range)
            
            # 估算
            client = container.user_client
            count = await self._estimate_message_count(client, source_chat_id, begin_date, end_date)
            
            # 显示时间
            time_str = time_config.get('display_text', '全部时间')
            
            return {
                'success': True,
                'count': count,
                'time_range': time_str,
                'source_title': source_chat_title,
                'target_title': target_chat_title
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

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
                
            # 直接存储在 [user_id][chat_id] 下，与 message_listener 保持一致
            self.user_sessions[user_id][chat_id] = session_data
            return True
        except Exception as e:
            logger.error(f"更新用户会话状态失败: {e}")
            return False

    async def get_available_rules(self, user_id: int) -> Dict[str, Any]:
        """获取可用的转发规则"""
        try:
            from models.models import ForwardRule
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            
            async with container.db.get_session() as session:
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

    async def get_chat_message_date_range(self, chat_id: int) -> Tuple[Optional[datetime], Optional[datetime]]:
        """获取会话中消息的日期范围（最早和最晚）"""
        try:
            client = container.user_client
            # 获取第一条和最后一条消息
            first_msgs = await client.get_messages(chat_id, limit=1, reverse=True)
            last_msgs = await client.get_messages(chat_id, limit=1)
            
            if not first_msgs or not last_msgs:
                return None, None
                
            return first_msgs[0].date, last_msgs[0].date
        except Exception as e:
            logger.error(f"获取会话日期范围失败: {e}")
            return None, None

    async def adjust_time_component(self, chat_id: int, side: str, field: str, delta: int):
        """微调时间分量"""
        import calendar
        from datetime import datetime
        
        tr = self.get_time_range(chat_id)
        now = datetime.now()
        
        # 获取当前值，如果为0则初始化为当前/默认值
        y = tr.get(f"{side}_year") or now.year
        m = tr.get(f"{side}_month") or now.month
        d = tr.get(f"{side}_day") or now.day
        h = tr.get(f"{side}_hour") or 0
        mn = tr.get(f"{side}_minute") or 0
        sc = tr.get(f"{side}_second") or 0
        
        if field == "year": y += delta
        elif field == "month":
            m += delta
            if m > 12: m = 1
            if m < 1: m = 12
        elif field == "day":
            d += delta
            _, max_d = calendar.monthrange(y, m if m > 0 else 1)
            if d > max_d: d = 1
            if d < 1: d = max_d
        elif field == "hour":
            h += delta
            if h > 23: h = 0
            if h < 0: h = 23
        elif field == "minute":
            mn += delta
            if mn > 59: mn = 0
            if mn < 0: mn = 59
        elif field == "second":
            sc += delta
            if sc > 59: sc = 0
            if sc < 0: sc = 59
            
        # 再次校验日期合法性（年份或月份变动可能导致天数非法）
        _, last_day = calendar.monthrange(y, m if m > 0 else 1)
        if d > last_day: d = last_day
        
        # 更新
        tr[f"{side}_year"] = y
        tr[f"{side}_month"] = m
        tr[f"{side}_day"] = d
        tr[f"{side}_hour"] = h
        tr[f"{side}_minute"] = mn
        tr[f"{side}_second"] = sc
        
        self.set_time_range(chat_id, tr)

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

    # --- 消息去重扫描与删除真实实现 ---

    async def scan_duplicate_messages(self, event, progress_callback=None):
        """扫描重复消息"""
        chat_id = event.chat_id
        user_id = event.sender_id
        
        # 增加缓存检查：如果无回调（即非手动点击重新扫描）且已有结果，则返回缓存
        if not progress_callback and chat_id in self.current_scan_results and self.current_scan_results[chat_id]:
            logger.info(f"💾 返回会话 {chat_id} 的去重扫描缓存结果")
            return self.current_scan_results[chat_id]
        
        time_config = self.get_time_range(user_id)
        begin_date, end_date, _, _ = parse_time_range_to_dates(time_config)
        
        duplicates = {} # signature -> [msg_ids]
        seen_sigs = {} # signature -> msg_id (first message seen)
        
        processed = 0
        client = container.user_client
        
        # 清除旧结果
        self.current_scan_results[chat_id] = {}
        
        try:
            # 优化：优先使用内容哈希以增加准确性（能识别重复上传的文件）
            # 使用 reverse=True 从旧到新扫描
            async for message in client.iter_messages(chat_id, offset_date=begin_date, reverse=True):
                # 检查结束时间
                if end_date and message.date > end_date.replace(tzinfo=timezone.utc):
                    break
                    
                processed += 1
                
                # 使用内容哈希作为第一优先级，因为它更准确地识别文件内容
                from services.dedup import tools
                sig = tools.generate_content_hash(message)
                
                # 如果内容哈希失败，尝试使用签名 (doc_id 等)
                if not sig:
                    sig = tools.generate_signature(message)
                
                if sig:
                    if sig in seen_sigs:
                        if sig not in duplicates:
                            duplicates[sig] = []
                        duplicates[sig].append(message.id)
                    else:
                        seen_sigs[sig] = message.id
                
                # 进度回调
                if progress_callback and processed % 100 == 0:
                    await progress_callback(processed, len(duplicates))
            
            # 生成短 ID 映射，防止 Telegram Callback Data (64字节) 溢出
            session = self._get_user_session(chat_id)
            sig_mapping = {}
            for sig in duplicates:
                import hashlib
                short_id = hashlib.md5(sig.encode()).hexdigest()[:8]
                sig_mapping[short_id] = sig
            session['sig_mapping'] = sig_mapping

            self.current_scan_results[chat_id] = duplicates
            logger.info(f"✅ 扫描完成: 处理 {processed} 条，发现 {len(duplicates)} 组重复内容 (映射数: {len(sig_mapping)})")
            return duplicates
            
        except Exception as e:
            logger.error(f"扫描重复消息失败: {e}", exc_info=True)
            return {}

    async def delete_duplicate_messages(self, event, mode="all"):
        """删除重复消息"""
        chat_id = event.chat_id
        if chat_id not in self.current_scan_results:
            return False, "请先进行扫描"
            
        duplicates_map = self.current_scan_results[chat_id]
        if not duplicates_map:
            return True, "没有发现重复项"
            
        msg_ids_to_delete = []
        if mode == "all":
            for ids in duplicates_map.values():
                msg_ids_to_delete.extend(ids)
        else:
            # 从会话中获取手动选中的签名
            selected = self._get_user_session(chat_id).get('selected_signatures', [])
            for sig in selected:
                if sig in duplicates_map:
                    msg_ids_to_delete.extend(duplicates_map[sig])
                    
        if not msg_ids_to_delete:
            return False, "未发现或未选择任何重复项"
            
        # 记录到进度
        session = self._get_user_session(chat_id)
        session['delete_task'] = {
            "deleted": 0,
            "total": len(msg_ids_to_delete),
            "status": "running",
            "cancel_event": asyncio.Event()
        }
            
        # 启动后台删除任务
        asyncio.create_task(self._execute_batch_delete(chat_id, msg_ids_to_delete))
        return True, "已启动后台删除任务"

    async def _execute_batch_delete(self, chat_id, msg_ids):
        """批量删除执行循环"""
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
                    task['deleted'] = deleted
                    
                    # 避免触发 Flood 控制
                    await asyncio.sleep(1.0)
                except Exception as e:
                    logger.error(f"删除批次 {i} 失败: {e}")
                    await asyncio.sleep(5.0) # 出错时多等等
            
            if task['status'] == "running":
                task['status'] = "completed"
                
            # 清理该会话的扫描缓存
            if chat_id in self.current_scan_results:
                del self.current_scan_results[chat_id]
                
        except Exception as e:
            logger.error(f"批量删除任务崩溃: {e}", exc_info=True)
            if task: task['status'] = "failed"

    async def get_delete_progress(self, chat_id):
        """获取删除任务进度"""
        task = self._get_user_session(chat_id).get('delete_task')
        if not task:
            return {"deleted": 0, "total": 0, "status": "idle"}
        return {
            "deleted": task.get("deleted", 0),
            "total": task.get("total", 0),
            "status": task.get("status", "unknown")
        }

    async def get_selection_state(self, chat_id):
        """获取选中的签名列表"""
        return self._get_user_session(chat_id).get('selected_signatures', [])
    
    async def toggle_select_signature(self, chat_id, signature):
        """切换签名的选中状态"""
        session = self._get_user_session(chat_id)
        
        # [Critical Fix] 如果传入的是 short_id，则需要从映射中还原
        if 'sig_mapping' in session and signature in session['sig_mapping']:
            signature = session['sig_mapping'][signature]
            
        if 'selected_signatures' not in session:
            session['selected_signatures'] = []
            
        if signature in session['selected_signatures']:
            session['selected_signatures'].remove(signature)
        else:
            session['selected_signatures'].append(signature)

    def _signature_to_display_name(self, sig):
        """签名转可显示名称"""
        if ":" in str(sig):
            parts = str(sig).split(":", 1)
            return f"[{parts[0]}] {parts[1][:15]}..."
        return str(sig)[:20]

    async def stop_delete_task(self, chat_id):
        """停止删除任务"""
        task = self._get_user_session(chat_id).get('delete_task')
        if task and task.get('cancel_event'):
            task['cancel_event'].set()
            task['status'] = "cancelled"
            return True
        return False

    async def preview_history_messages(self, event, _sample=10, _collect_full=True, _max_collect=800):
        """预览历史消息 (真实采集示例)"""
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

    async def get_history_delay(self, chat_id):
        return self._get_user_session(chat_id).get('delay', 0)

    def is_auto_refresh_enabled(self, chat_id):
        return False

    async def set_auto_refresh(self, chat_id, enabled, message_id):
        pass

    async def preview_session_messages_by_filter(self, event, limit=10):
        """预览符合当前筛选条件的会话消息 (UIRE-2.0)"""
        chat_id = event.chat_id
        user_id = event.sender_id
        time_config = self.get_time_range(user_id)
        begin_date, end_date, _, _ = parse_time_range_to_dates(time_config)
        
        client = container.user_client
        samples = []
        count = 0
        try:
            async for message in client.iter_messages(chat_id, offset_date=begin_date, reverse=True):
                if end_date and message.date > end_date.replace(tzinfo=timezone.utc):
                    break
                count += 1
                if len(samples) < limit:
                    samples.append(message)
            return count, samples
        except Exception as e:
            logger.error(f"Preview session messages failed: {e}")
            return 0, []

    async def delete_session_messages_by_filter(self, event):
        """批量删除符合筛选条件的会话消息 (UIRE-2.0)"""
        chat_id = event.chat_id
        user_id = event.sender_id
        time_config = self.get_time_range(user_id)
        begin_date, end_date, _, _ = parse_time_range_to_dates(time_config)
        
        client = container.user_client
        msg_ids = []
        try:
            async for message in client.iter_messages(chat_id, offset_date=begin_date, reverse=True):
                if end_date and message.date > end_date.replace(tzinfo=timezone.utc):
                    break
                msg_ids.append(message.id)
            
            if not msg_ids:
                return True, "没有匹配的消息"
            
            # 记录到进度
            session = self._get_user_session(user_id)
            session['delete_task'] = {
                "deleted": 0,
                "total": len(msg_ids),
                "status": "running",
                "cancel_event": asyncio.Event()
            }
                
            # 启动后台删除任务
            asyncio.create_task(self._execute_batch_delete(chat_id, msg_ids))
            return True, "已启动后台清理任务"
        except Exception as e:
            logger.error(f"Batch delete failed: {e}")
            return False, str(e)

    async def get_selection_state(self, chat_id):
        """获取选中状态"""
        return self._get_user_session(chat_id).get('selected_signatures', [])

    async def toggle_select_signature(self, chat_id, sig_id):
        """切换选中签名 (支持短 ID)"""
        session = self._get_user_session(chat_id)
        if 'selected_signatures' not in session:
            session['selected_signatures'] = []
            
        # 尝试通过短 ID 映射找回原始签名
        sig_mapping = session.get('sig_mapping', {})
        real_sig = sig_mapping.get(sig_id, sig_id)
        
        if real_sig in session['selected_signatures']:
            session['selected_signatures'].remove(real_sig)
        else:
            session['selected_signatures'].append(real_sig)
        return True


system_session_service = SessionService()
# Alias for backward compatibility (external modules might import session_service)
session_service = system_session_service
# Alias for session_manager transition
session_manager = system_session_service
