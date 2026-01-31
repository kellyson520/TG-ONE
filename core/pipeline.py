import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Any, Callable, Dict, Optional
from core.context import trace_id_var
from core.logging import short_id

logger = logging.getLogger(__name__)

@dataclass
class MessageContext:
    client: Any                 # Telethon Client
    task_id: int                # TaskQueue ID
    chat_id: int
    message_id: int
    message_obj: Any            # Telethon Message 对象
    
    # 流程控制
    rules: List[Any] = field(default_factory=list)
    is_terminated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None # 记录处理过程中的错误
    failed_rules: List[int] = field(default_factory=list) # 记录失败的规则ID
    
    # 媒体组支持
    is_group: bool = False
    group_messages: List[Any] = field(default_factory=list)
    related_tasks: List[Any] = field(default_factory=list)
    
    # 模拟模式
    is_sim: bool = False
    trace: List[Dict[str, Any]] = field(default_factory=list)

    def log_trace(self, step: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        if self.is_sim:
            self.trace.append({
                "step": step,
                "status": status,
                "details": details or {},
                "timestamp": 0 # Placeholder
            })

class Middleware(ABC):
    @abstractmethod
    async def process(self, ctx: MessageContext, _next_call: Callable) -> None:
        pass

class Pipeline:
    def __init__(self) -> None:
        self.middlewares: List[Middleware] = []

    def add(self, middleware: Middleware) -> "Pipeline":
        self.middlewares.append(middleware)
        return self

    async def execute(self, ctx: MessageContext) -> None:
        # 生成唯一标识符 (Trace ID)
        trace_id = uuid.uuid4().hex[:8]
        token = trace_id_var.set(trace_id)
        
        # 注入到 metadata 以便后续使用
        ctx.metadata["trace_id"] = trace_id

        try:
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(ctx.chat_id)
            logger.debug(f"🔄 [Pipeline] 开始执行流程，TraceID={trace_id}, 任务ID={short_id(ctx.task_id)}, 来源={chat_display}({ctx.chat_id}), 消息ID={ctx.message_id}")
            
            async def _next(index: int) -> None:
                if index < len(self.middlewares) and not ctx.is_terminated:
                    middleware_name = type(self.middlewares[index]).__name__
                    logger.debug(f"🔀 [Pipeline] 执行中间件 {middleware_name}，TraceID={trace_id}")
                    
                    try:
                        await self.middlewares[index].process(ctx, lambda: _next(index + 1))
                        logger.debug(f"✅ [Pipeline] 中间件 {middleware_name} 执行成功，TraceID={trace_id}")
                    except Exception as e:
                        logger.error(f"❌ [Pipeline] 中间件 {middleware_name} 执行失败，TraceID={trace_id}，错误={e}", exc_info=True)
                        ctx.error = e
                        ctx.is_terminated = True
                        raise e 
            await _next(0)
            
            if ctx.is_terminated:
                logger.debug(f"⚠️ [Pipeline] 流程终止，TraceID={trace_id}")
            else:
                logger.info(f"✅ [Pipeline] 流程执行完成，TraceID={trace_id}")
                
        except Exception as e:
            logger.error(f"❌ [Pipeline] 整体流程执行失败，TraceID={trace_id}，错误={e}", exc_info=True)
            raise
        finally:
            trace_id_var.reset(token)