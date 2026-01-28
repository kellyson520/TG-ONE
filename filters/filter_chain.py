import logging
import asyncio
from typing import List, Protocol, runtime_checkable
from filters.base_filter import BaseFilter
from filters.context import MessageContext

logger = logging.getLogger(__name__)

@runtime_checkable
class ExecutionNode(Protocol):
    async def execute(self, context: MessageContext) -> bool: ...

class FilterNode:
    """包装单个过滤器的执行节点"""
    def __init__(self, filter_obj: BaseFilter):
        self.filter = filter_obj
    
    @property
    def name(self):
        return self.filter.name

    async def execute(self, context: MessageContext) -> bool:
        try:
            # Result Caching (Simple implementation)
            # If context has a unique signature for this filter execution, check cache.
            # Currently context doesn't have a reliable hash for mutation state.
            # So pass through.
            
            should_continue = await asyncio.wait_for(
                self.filter.process(context),
                timeout=30.0 # Increased timeout for AI filters
            )
            if not should_continue:
                logger.info(f"过滤器 {self.filter.name} 中断了处理链")
                return False
            return True
        except asyncio.TimeoutError:
            logger.error(f"过滤器 {self.filter.name} 执行超时（30秒）")
            context.errors.append(f"过滤器 {self.filter.name} 执行超时")
            return False
        except Exception as e:
            logger.error(f"过滤器 {self.filter.name} 处理出错: {e}", exc_info=True)
            context.errors.append(f"过滤器 {self.filter.name} 错误: {e}")
            return False

class ParallelNode:
    """并行执行的一组过滤器（仅限只读检查类过滤器）"""
    def __init__(self, nodes: List[ExecutionNode]):
        self.nodes = nodes
    
    async def execute(self, context: MessageContext) -> bool:
        if not self.nodes:
            return True
            
        logger.debug(f"并行执行 {len(self.nodes)} 个过滤器...")
        # 针对只读检查，并发执行
        results = await asyncio.gather(*[n.execute(context) for n in self.nodes], return_exceptions=True)
        
        # 检查结果
        success = True
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"并行节点执行异常: {res}")
                context.errors.append(f"Parallel execution error: {str(res)}")
                success = False
            elif res is False:
                success = False
        
        return success

class FilterChain:
    """
    过滤器链 2.0 (AST-like Execution Plan)
    支持顺序执行与并行执行节点的组合
    """
    
    def __init__(self):
        self.nodes: List[ExecutionNode] = []
        self._legacy_filters_list: List[BaseFilter] = [] # For backward compatibility in inspection
        
    @property
    def filters(self) -> List[BaseFilter]:
        """Backwards compatibility for inspection"""
        return self._legacy_filters_list

    def add_filter(self, filter_obj: BaseFilter):
        """添加单个顺序过滤器 (兼容旧 API)"""
        node = FilterNode(filter_obj)
        self.nodes.append(node)
        self._legacy_filters_list.append(filter_obj)
        return self
    
    def add_parallel_group(self, filters: List[BaseFilter]):
        """添加并行执行组"""
        if not filters:
            return self
        
        nodes = [FilterNode(f) for f in filters]
        self.nodes.append(ParallelNode(nodes))
        self._legacy_filters_list.extend(filters)
        return self

    async def process(self, client, event, chat_id, rule):
        """Legacy Entry Point"""
        context = MessageContext(client, event, chat_id, rule)
        return await self.process_context(context)

    async def process_context(self, context: MessageContext) -> bool:
        """执行过滤器链"""
        logger.info(f"开始过滤器链处理 (Plan Nodes: {len(self.nodes)}) [TraceID: {getattr(context, 'trace_id', 'N/A')}]")
        
        for i, node in enumerate(self.nodes):
            if not await node.execute(context):
                logger.info(f"节点 {i} ({type(node).__name__}) 拦截了执行")
                return False
                
        logger.info("过滤器链处理完成")
        return True
