
import logging

logger = logging.getLogger(__name__)

class UnifiedForwardManager:
    """统一转发管理器的占位类，用于兼容 legacy 代码"""
    
    async def forward_single_message(self, source_chat_id, target_chat_id, message_id, rule_id, forward_type):
        """模拟转发单个消息"""
        logger.info(f"Mock forwarding message {message_id} from {source_chat_id} to {target_chat_id} for rule {rule_id}")
        return True

_instance = None

def get_forward_manager():
    global _instance
    if _instance is None:
        _instance = UnifiedForwardManager()
    return _instance
