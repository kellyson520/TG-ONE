"""
会话管理服务层
处理历史消息任务、时间范围设置等会话相关业务逻辑
"""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

class SessionService:
    """会话管理业务逻辑服务"""
    
    async def get_history_task_status(self, user_id: int) -> Dict[str, Any]:
        """获取历史任务状态"""
        try:
            from handlers.button.session_management import session_manager
            
            # 获取任务进度（协程）
            progress = await session_manager.get_history_progress(user_id)
            
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
            logger.error(f"获取历史任务状态失败: {e}")
            return {
                'has_task': False,
                'status': 'error',
                'progress': None,
                'error': str(e)
            }
    
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
    
    async def get_available_rules(self, user_id: int) -> Dict[str, Any]:
        """获取可用的转发规则 (原生异步)"""
        try:
            from models.models import ForwardRule
            from core.container import container
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            
            async with container.db.session() as session:
                # 预加载关联的聊天和关键字，避免延迟加载错误
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
            return {
                'success': False,
                'error': str(e),
                'rules': [],
                'total_count': 0
            }
    
    async def get_selected_rule(self, user_id: int) -> Dict[str, Any]:
        """获取当前选中的规则"""
        try:
            from handlers.button.session_management import session_manager
            
            rule_id = await session_manager.get_selected_rule(user_id)
            
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
            
            # 统一为渲染器/调用方期望的结构：提供 'rule' 对象
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
                # 兜底：最简结构，避免上层因缺少键报错
                rule_obj = {'id': rule_id, 'source_chat': {'title': 'Unknown'}, 'target_chat': {'title': 'Unknown'}, 'settings': {}}
            return {
                'has_selection': True,
                'rule': rule_obj,
                'rule_id': rule_id
            }
            
        except Exception as e:
            logger.error(f"获取选中规则失败: {e}")
            return {
                'has_selection': False,
                'rule': None,
                'error': str(e)
            }
    
    async def set_selected_rule(self, user_id: int, rule_id: int) -> Dict[str, Any]:
        """设置选中的规则"""
        try:
            from handlers.button.session_management import session_manager
            
            # 验证规则是否存在
            from services.rule_management_service import rule_management_service
            rule_detail = await rule_management_service.get_rule_detail(rule_id)
            
            if not rule_detail['success']:
                return {
                    'success': False,
                    'error': f'规则 {rule_id} 不存在'
                }
            
            # 设置选中规则
            await session_manager.set_selected_rule(user_id, rule_id)
            
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
                'success': True,
                'rule_id': rule_id,
                'rule': rule_obj,
                'message': f'已选择规则 {rule_id}'
            }
            
        except Exception as e:
            logger.error(f"设置选中规则失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_time_range_config(self, user_id: int) -> Dict[str, Any]:
        """获取时间范围配置"""
        try:
            from handlers.button.session_management import session_manager
            
            time_range = session_manager.get_time_range(user_id)
            
            # 提供默认值
            if time_range is None:
                time_range = {
                    'start_year': 0, 'start_month': 0, 'start_day': 0,
                    'start_hour': 0, 'start_minute': 0, 'start_second': 0,
                    'end_year': 0, 'end_month': 0, 'end_day': 0,
                    'end_hour': 0, 'end_minute': 0, 'end_second': 0
                }
            
            # 判断是否为全零（全部消息）
            is_all_messages = all(time_range.get(key, 0) == 0 for key in time_range.keys())
            
            try:
                from utils.time_range import format_time_range_display
                display_text = format_time_range_display(time_range)
            except Exception:
                display_text = self._format_time_range_display(time_range, is_all_messages)
            return {
                'success': True,
                'time_range': time_range,
                'is_all_messages': is_all_messages,
                'display_text': display_text
            }
            
        except Exception as e:
            logger.error(f"获取时间范围配置失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'time_range': {},
                'is_all_messages': True,
                'display_text': '时间范围加载失败'
            }
    
    def _format_time_range_display(self, time_range: Dict[str, int], is_all_messages: bool) -> str:
        """已废弃：保留向后兼容。新实现统一用 utils.time_range.format_time_range_display。"""
        try:
            from utils.time_range import format_time_range_display
            return format_time_range_display(time_range)
        except Exception:
            return "全部时间 (将获取全部消息)" if is_all_messages else "自定义时间范围"
    
    def _format_datetime_text(self, year: int, month: int, day: int, hour: int, minute: int, second: int) -> str:
        """格式化单个时间点的显示文本"""
        if year == 0:
            return "最早"
        return f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    
    async def update_time_range(self, user_id: int, **time_params) -> Dict[str, Any]:
        """更新时间范围配置"""
        try:
            from handlers.button.session_management import session_manager
            
            # 获取当前配置
            current_range = session_manager.get_time_range(user_id) or {}
            
            # 更新指定参数
            updated_range = {**current_range, **time_params}
            
            # 设置新的时间范围
            session_manager.set_time_range(user_id, updated_range)
            
            return {
                'success': True,
                'time_range': updated_range,
                'message': '时间范围已更新'
            }
            
        except Exception as e:
            logger.error(f"更新时间范围失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_delay_settings(self, user_id: int) -> Dict[str, Any]:
        """获取延迟设置"""
        try:
            from handlers.button.session_management import session_manager
            
            delay = session_manager.get_delay_setting(user_id)
            
            return {
                'success': True,
                'delay_seconds': delay,
                'delay_text': self._format_delay_text(delay)
            }
            
        except Exception as e:
            logger.error(f"获取延迟设置失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'delay_seconds': 1,
                'delay_text': '1秒'
            }
    
    def _format_delay_text(self, delay: int) -> str:
        """格式化延迟显示文本"""
        if delay == 0:
            return "无延迟"
        elif delay < 60:
            return f"{delay}秒"
        else:
            return f"{delay // 60}分{delay % 60}秒"
    
    async def update_delay_setting(self, user_id: int, delay_seconds: int) -> Dict[str, Any]:
        """更新延迟设置"""
        try:
            from handlers.button.session_management import session_manager
            
            if delay_seconds < 0 or delay_seconds > 3600:  # 最大1小时
                return {
                    'success': False,
                    'error': '延迟时间必须在0-3600秒之间'
                }
            
            session_manager.set_delay_setting(user_id, delay_seconds)
            
            return {
                'success': True,
                'delay_seconds': delay_seconds,
                'delay_text': self._format_delay_text(delay_seconds),
                'message': f'延迟已设置为 {self._format_delay_text(delay_seconds)}'
            }
            
        except Exception as e:
            logger.error(f"更新延迟设置失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def start_history_task(self, user_id: int) -> Dict[str, Any]:
        """启动历史消息任务"""
        try:
            from handlers.button.session_management import session_manager
            
            # 获取选中的规则
            rule_selection = await self.get_selected_rule(user_id)
            if not rule_selection['has_selection']:
                return {
                    'success': False,
                    'error': '请先选择一个转发规则'
                }
            
            # 获取时间范围
            time_config = await self.get_time_range_config(user_id)
            if not time_config['success']:
                return {
                    'success': False,
                    'error': '获取时间范围配置失败'
                }
            
            # 启动任务（返回可能是 (bool, message) 或 dict）
            try:
                result = await session_manager.start_history_task(user_id)
                logger.info(f"session_manager.start_history_task 返回结果: {result}")
            except Exception as start_error:
                logger.error(f"调用 session_manager.start_history_task 时发生异常: {start_error}", exc_info=True)
                return {
                    'success': False,
                    'error': f'启动任务时发生异常: {str(start_error)}'
                }
            
            success = False
            message = '任务启动'
            task_id = None
            estimated_total = 0
            if isinstance(result, tuple) and len(result) >= 1:
                success = bool(result[0])
                message = result[1] if len(result) > 1 else message
            elif isinstance(result, dict):
                success = bool(result.get('success', False))
                message = result.get('message', message)
                task_id = result.get('task_id')
                estimated_total = int(result.get('estimated_total', 0) or 0)
            else:
                logger.warning(f"session_manager.start_history_task 返回了意外的结果类型: {type(result)}, 值: {result}")
            return {
                'success': success,
                'task_id': task_id,
                'message': message,
                'estimated_total': estimated_total
            }
            
        except Exception as e:
            logger.error(f"启动历史任务失败: {e}", exc_info=True)
            # 确保 error 字段不为空且有意义
            error_msg = str(e) if str(e).strip() else "未知错误"
            return {
                'success': False,
                'error': error_msg
            }
    
    async def cancel_history_task(self, user_id: int) -> Dict[str, Any]:
        """取消历史消息任务"""
        try:
            from handlers.button.session_management import session_manager
            
            result = await session_manager.stop_history_task(user_id)
            
            return {
                'success': result,
                'message': '任务已取消' if result else '取消任务失败'
            }
            
        except Exception as e:
            logger.error(f"取消历史任务失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def update_user_state(self, user_id: int, chat_id: int, state: str, rule_id: int, extra: Dict[str, Any] = None):
        """更新用户会话状态 (替代 MenuController 直接操作)"""
        try:
            from handlers.button.session_management import session_manager
            
            if user_id not in session_manager.user_sessions:
                session_manager.user_sessions[user_id] = {}
            
            session_data = {
                "state": state,
                "rule_id": rule_id,
                "message": {"rule_id": rule_id}
            }
            if extra:
                session_data.update(extra)
                
            session_manager.user_sessions[user_id][chat_id] = session_data
            return True
        except Exception as e:
            logger.error(f"更新用户会话状态失败: {e}")
            return False

# 全局服务实例
session_service = SessionService()
