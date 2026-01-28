import logging
from abc import ABC, abstractmethod
from models.models import MediaSignature
from repositories.db_context import async_safe_db_operation
from core.helpers.error_handler import handle_errors, log_execution


logger = logging.getLogger(__name__)

class BaseFilter(ABC):
    """
    基础过滤器类，定义过滤器接口
    增强版本：集成统一的错误处理和数据库管理
    """
    
    def __init__(self, name=None):
        """
        初始化过滤器
        
        Args:
            name: 过滤器名称，如果为None则使用类名
        """
        self.name = name or self.__class__.__name__
        
    @handle_errors(default_return=False)
    @log_execution()
    async def process(self, context):
        """
        处理消息上下文 - 带统一错误处理
        
        Args:
            context: 包含消息处理所需所有信息的上下文对象
            
        Returns:
            bool: 表示是否应该继续处理消息
        """
        logger.info(f"开始执行过滤器: {self.name}")
        result = await self._process(context)
        logger.info(f"过滤器 {self.name} 处理结果: {'通过' if result else '不通过'}")
        return result
    
    @abstractmethod
    async def _process(self, context):
        """
        具体的处理逻辑，子类需要实现
        
        Args:
            context: 包含消息处理所需所有信息的上下文对象
            
        Returns:
            bool: 表示是否应该继续处理消息
        """
        pass 

    @handle_errors(default_return=False)
    async def record_media_signature(self, chat_id: str, signature: str, message_id: int = None):
        """
        记录媒体签名（去重用） - 使用统一的数据库管理
        
        Args:
            chat_id: 聊天ID
            signature: 媒体签名
            message_id: 消息ID（可选）
            
        Returns:
            bool: 是否成功记录（如果已存在则返回False）
        """
        from sqlalchemy import select
        
        async def operation(session):
            # 已存在则跳过
            stmt = select(MediaSignature).filter_by(
                chat_id=str(chat_id), 
                signature=signature
            ).limit(1)
            result = await session.execute(stmt)
            exists = result.scalar_one_or_none()
            if exists:
                return False
            
            rec = MediaSignature(
                chat_id=str(chat_id), 
                signature=signature, 
                message_id=message_id
            )
            session.add(rec)
            return True
        
        return await async_safe_db_operation(operation, default_return=False)
    
    @handle_errors(default_return=None)
    async def safe_db_query(self, query_func):
        """
        安全的数据库查询操作
        为子类提供便捷的数据库查询方法
        
        Args:
            query_func: 接受session参数的异步查询函数
            
        Returns:
            查询结果或None
        """
        return await async_safe_db_operation(query_func, default_return=None)
    
    @handle_errors(default_return=False)
    async def safe_db_update(self, update_func):
        """
        安全的数据库更新操作
        为子类提供便捷的数据库更新方法
        
        Args:
            update_func: 接受session参数的异步更新函数
            
        Returns:
            bool: 是否更新成功
        """
        return await async_safe_db_operation(update_func, default_return=False)
