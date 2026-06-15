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
from core.helpers.time_range import parse_time_range_to_dates
from services.forward_settings_service import forward_settings_service
from services.session_time import SessionTimeMixin
from services.session_history import SessionHistoryMixin
from services.session_dedup import SessionDedupMixin

logger = logging.getLogger(__name__)


class SessionService(SessionTimeMixin, SessionHistoryMixin, SessionDedupMixin):
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

        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.current_scan_results: Dict[Any, Any] = {}
        self._scan_result_timestamps: Dict[Any, datetime] = {}
        self._scan_result_ttl_seconds = 1800
        self._scan_result_max_chats = 10

        tombstone.register(
            "session_service", self._get_state_dump, self._restore_state_dump
        )
        self._initialized = True
        logger.info("SessionService initialized with tombstone support")

    def _get_state_dump(self):
        serializable_sessions = {}
        for uid, session in self.user_sessions.items():
            s = session.copy()
            if 'history_task' in s:
                task_info = s['history_task'].copy()
                task_info.pop('cancel_event', None)
                task_info.pop('future', None)
                s['history_task'] = task_info
            serializable_sessions[str(uid)] = s
        return {
            "user_sessions": serializable_sessions,
            "current_scan_results": {},
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
                        if k.isdigit() or (k.startswith('-') and k[1:].isdigit()):
                            processed_content[int(k)] = v
                        else:
                            processed_content[k] = v
                    self.user_sessions[uid] = processed_content
                except ValueError:
                    logger.warning(f"跳过无效的用户ID key: {uid_str}")
            self.current_scan_results = {}
            self._scan_result_timestamps = {}
            logger.info(f"🔥 SessionService 恢复了 {len(self.user_sessions)} 个用户会话")

    def _get_user_session(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        return self.user_sessions[user_id]

    def get_chat_session(self, user_id: int, chat_id: int) -> Dict[str, Any]:
        user_session = self._get_user_session(user_id)
        chat_session = user_session.get(chat_id)
        if not isinstance(chat_session, dict):
            chat_session = {}
            user_session[chat_id] = chat_session
        return chat_session

    def set_user_session(self, user_id: int, chat_id: int, data: Dict[str, Any]) -> None:
        self._get_user_session(user_id)[chat_id] = data or {}

    def clear_user_session(self, user_id: int, chat_id: Optional[int] = None) -> None:
        if user_id not in self.user_sessions:
            return
        if chat_id is None:
            self.user_sessions.pop(user_id, None)
            return
        self.user_sessions[user_id].pop(chat_id, None)
        if not self.user_sessions[user_id]:
            self.user_sessions.pop(user_id, None)

    def _prune_scan_results(self) -> None:
        now = datetime.utcnow()
        expired = [
            chat_id for chat_id, created_at in self._scan_result_timestamps.items()
            if (now - created_at).total_seconds() > self._scan_result_ttl_seconds
        ]
        for chat_id in expired:
            self.current_scan_results.pop(chat_id, None)
            self._scan_result_timestamps.pop(chat_id, None)
        overflow = len(self.current_scan_results) - self._scan_result_max_chats
        if overflow > 0:
            ordered = sorted(self._scan_result_timestamps.items(), key=lambda item: item[1])
            for chat_id, _ in ordered[:overflow]:
                self.current_scan_results.pop(chat_id, None)
                self._scan_result_timestamps.pop(chat_id, None)

    def _get_cached_scan_result(self, chat_id: int):
        self._prune_scan_results()
        return self.current_scan_results.get(chat_id)

    def _set_scan_result(self, chat_id: int, result: Dict[str, Any]) -> None:
        self.current_scan_results[chat_id] = result
        self._scan_result_timestamps[chat_id] = datetime.utcnow()
        self._prune_scan_results()

    def _clear_scan_result(self, chat_id: int) -> None:
        self.current_scan_results.pop(chat_id, None)
        self._scan_result_timestamps.pop(chat_id, None)

    def clear_scan_result(self, chat_id: int) -> None:
        self._clear_scan_result(chat_id)

    def keep_duplicate_messages(self, event) -> Tuple[bool, str]:
        chat_id = event.chat_id
        self._clear_scan_result(chat_id)
        session = self._get_user_session(chat_id)
        session.pop('selected_signatures', None)
        session.pop('sig_mapping', None)
        return True, "已保留重复项"

    async def get_selected_rule(self, user_id: int) -> Dict[str, Any]:
        try:
            rule_id = self._get_user_session(user_id).get('selected_rule_id')
            if rule_id is None:
                return {'has_selection': False, 'rule': None, 'message': '请先选择一个转发规则'}
            from services.rule_management_service import rule_management_service
            rule_detail = await rule_management_service.get_rule_detail(rule_id)
            if not rule_detail['success']:
                return {'has_selection': False, 'rule': None, 'error': f'规则 {rule_id} 不存在或已被删除'}
            try:
                rule_obj = {
                    'id': rule_id,
                    'source_chat': {'title': rule_detail.get('source_chat') or 'Unknown', 'telegram_chat_id': None},
                    'target_chat': {'title': rule_detail.get('target_chat') or 'Unknown', 'telegram_chat_id': None},
                    'settings': {
                        'enabled': bool(rule_detail.get('enabled', True)),
                        'enable_dedup': bool(rule_detail.get('enable_dedup', False)),
                    },
                    'keywords': [], 'replace_rules': [],
                }
            except Exception:
                rule_obj = {'id': rule_id, 'source_chat': {'title': 'Unknown'}, 'target_chat': {'title': 'Unknown'}, 'settings': {}}
            return {'has_selection': True, 'rule': rule_obj, 'rule_id': rule_id}
        except Exception as e:
            logger.error(f"获取选中规则失败: {e}")
            return {'has_selection': False, 'rule': None, 'error': str(e)}

    async def set_selected_rule(self, user_id: int, rule_id: int) -> Dict[str, Any]:
        try:
            from services.rule_management_service import rule_management_service
            rule_detail = await rule_management_service.get_rule_detail(rule_id)
            if not rule_detail['success']:
                return {'success': False, 'error': f'规则 {rule_id} 不存在'}
            self._get_user_session(user_id)['selected_rule_id'] = rule_id
            try:
                rule_obj = {
                    'id': rule_id,
                    'source_chat': {'title': rule_detail.get('source_chat') or 'Unknown'},
                    'target_chat': {'title': rule_detail.get('target_chat') or 'Unknown'},
                }
            except Exception:
                rule_obj = {}
            return {'success': True, 'rule_id': rule_id, 'rule': rule_obj, 'message': f'已选择规则 {rule_id}'}
        except Exception as e:
            logger.error(f"设置选中规则失败: {e}")
            return {'success': False, 'error': str(e)}

    async def update_user_state(self, user_id: int, chat_id: int, state: str, rule_id: int, extra: Dict[str, Any] = None):
        try:
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {}
            session_data = {"state": state, "rule_id": rule_id, "message": {"rule_id": rule_id}}
            if extra:
                session_data.update(extra)
            self.user_sessions[user_id][chat_id] = session_data
            return True
        except Exception as e:
            logger.error(f"更新用户会话状态失败: {e}")
            return False

    async def get_available_rules(self, user_id: int) -> Dict[str, Any]:
        try:
            from models.models import ForwardRule
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            async with container.db.get_session() as session:
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
                return {'success': True, 'rules': rules_data, 'total_count': len(rules_data)}
        except Exception as e:
            logger.error(f"获取可用规则失败: {e}")
            return {'success': False, 'error': str(e), 'rules': [], 'total_count': 0}

    async def get_chat_message_date_range(self, chat_id: int) -> Tuple[Optional[datetime], Optional[datetime]]:
        try:
            client = container.user_client
            first_msgs = await client.get_messages(chat_id, limit=1, reverse=True)
            last_msgs = await client.get_messages(chat_id, limit=1)
            if not first_msgs or not last_msgs:
                return None, None
            return first_msgs[0].date, last_msgs[0].date
        except Exception as e:
            logger.error(f"获取会话日期范围失败: {e}")
            return None, None


system_session_service = SessionService()
session_service = system_session_service
session_manager = system_session_service
