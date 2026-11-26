from core.pipeline import Middleware
from filters.factory import get_filter_chain_factory
from filters.context import MessageContext
import logging

logger = logging.getLogger(__name__)

class FilterMiddleware(Middleware):
    def __init__(self):
        # 初始化过滤器工厂
        self.filter_factory = get_filter_chain_factory()

    async def process(self, ctx, next_call):
        """
        处理消息过滤 (完全由 Factory 驱动)
        
        Args:
            ctx: 消息上下文
            next_call: 下一个中间件的调用函数
        """
        from core.helpers.id_utils import get_display_name_async
        chat_display = await get_display_name_async(ctx.chat_id)
        logger.info(f"🔍 [Pipeline-Filter] 开始处理: 任务ID={ctx.task_id}, 来源={chat_display}({ctx.chat_id}), 消息ID={ctx.message_id}")
        
        # 如果没有规则，直接终止处理
        if not ctx.rules:
            chat_display = await get_display_name_async(ctx.chat_id)
            logger.info(f"⚠️ [Pipeline-Filter] 无规则可用，流程结束: 来源={chat_display}({ctx.chat_id})")
            ctx.is_terminated = True
            return
        
        # 过滤规则
        passed_rules = []
        for rule in ctx.rules:
            logger.info(f"🎯 [过滤器] 正在处理规则 {rule.id}")
            
            # 1. 动态获取过滤器链
            chain = self.filter_factory.create_chain_for_rule(rule)
            
            # 2. 创建上下文
            filter_context = await self._create_filter_context(ctx, rule)
            
            # 3. 执行过滤链
            should_process = await chain.process_context(filter_context)
            
            if should_process:
                passed_rules.append(rule)
                # 保存修改后的文本供 Sender 使用
                final_text = getattr(filter_context, 'message_text', None)
                original_text = ctx.message_obj.text if hasattr(ctx.message_obj, 'text') else ''
                if final_text != original_text:
                    if not hasattr(ctx, 'metadata'):
                        ctx.metadata = {}
                    ctx.metadata[f'modified_text_{rule.id}'] = final_text
                    logger.info(f"📝 [过滤器] 规则 {rule.id} 修改文本成功")
                else:
                    logger.info(f"✅ [过滤器] 规则 {rule.id} 通过所有过滤条件")
            else:
                logger.info(f"🚫 [过滤器] 规则 {rule.id} 被链条拦截")
                # 计算耗时
                import time
                duration = (time.time() - ctx.start_time) * 1000 if hasattr(ctx, 'start_time') else 0
                
                # 发布过滤事件，用于统计上报
                if getattr(self.filter_factory, 'container', None):
                    from core.helpers.msg_utils import detect_message_type
                    await self.filter_factory.container.bus.publish("FORWARD_FILTERED", {
                        "rule_id": rule.id,
                        "msg_id": ctx.message_id,
                        "reason": str(filter_context.errors[0]) if filter_context.errors else "Unknown",
                        "msg_text": ctx.message_obj.text if hasattr(ctx.message_obj, 'text') else "",
                        "msg_type": detect_message_type(ctx.message_obj),
                        "duration": duration
                    })
                else:
                    logger.warning(f"由于 filter_factory.container 未设置，跳过 FORWARD_FILTERED 事件发布 (Rule={rule.id})")
                # 记录失败原因到 ctx (可选)
                if not hasattr(ctx, 'failed_rules'):
                    ctx.failed_rules = []
                # [FIX] MessageContext.failed_rules 的类型是 List[int]，
                # 下游 dedup 用 `rule_id in ctx.failed_rules` 判断。
                # 原来塞 dict 导致回滚永远不触发，发送失败的消息会被永久判重复。
                ctx.failed_rules.append(rule.id)
                ctx.metadata.setdefault('failed_rule_reasons', {})[rule.id] = filter_context.errors
        
        # 更新上下文规则
        ctx.rules = passed_rules
        
        if ctx.rules:
            logger.info(f"✅ [过滤器] 最终有 {len(ctx.rules)} 条规则通过，继续处理")
            await next_call()
        else:
            logger.info(f"⚠️ [过滤器] 所有规则均被过滤器拦截，流程结束")
            ctx.is_terminated = True
    
    async def _create_filter_context(self, ctx, rule) -> MessageContext:
        """
        创建适用于过滤器的 MessageContext
        """
        # 构建 Mock Event (适配 MessageContext 构造函数)
        # MessageContext 内部使用 event.message.text / event.message.grouped_id 等
        # 确保 Mock Event 结构兼容
        class MockEvent:
            message = ctx.message_obj
            chat_id = ctx.chat_id
            
        mock_event = MockEvent()
        
        # 初始化标准上下文
        # MessageContext(client, event, chat_id, rule)
        context = MessageContext(ctx.client, mock_event, ctx.chat_id, rule)
        
        # 补充额外信息 (Pipeline Context 特有)
        context.is_media_group = getattr(ctx, 'is_group', False)
        context.media_group_messages = getattr(ctx, 'group_messages', [])
        
        # 传递 Simulation 标记
        if hasattr(ctx, 'is_sim'):
            context.is_sim = ctx.is_sim
            
        # 传递历史任务标记
        if ctx.metadata.get('is_history'):
            context.is_history = True
            
        return context