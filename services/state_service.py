"""
用户状态服务
负责管理机器人的交互状态（FSM）
[Refactor] 从 managers/state_manager.py 迁移并增强
"""
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class StateService:
    """用户状态服务"""
    
    def __init__(self):
        # {(user_id, chat_id): "state_name"}
        self._states: Dict[Tuple[int, int], str] = {}

    def set_state(self, user_id: int, chat_id: int, state: str, message: Any = None, state_type: Any = None):
        """设置用户在特定聊天中的状态"""
        self._states[(user_id, chat_id)] = state
        logger.debug(f"User {user_id} in {chat_id} set to state: {state}")

    def get_state(self, user_id: int, chat_id: int) -> Tuple[Optional[str], Any, Any]:
        """获取用户在特定聊天中的状态"""
        return self._states.get((user_id, chat_id)), None, None

    def clear_state(self, user_id: int, chat_id: int):
        """清除用户状态"""
        if (user_id, chat_id) in self._states:
            del self._states[(user_id, chat_id)]
            logger.debug(f"User {user_id} in {chat_id} state cleared")
    
    async def clear_state_async(self, user_id: int, chat_id: int):
        """异步清除用户状态 (保持兼容性)"""
        self.clear_state(user_id, chat_id)

# 全局单例
state_service = StateService()
