from core.pipeline import Middleware, MessageContext
from ai import get_ai_provider # 假设 ai/__init__.py 暴露了这个工厂函数
import logging

logger = logging.getLogger(__name__)

class AIMiddleware(Middleware):
    async def process(self, ctx: MessageContext, next_call):
        # 1. 检查是否有规则启用了 AI
        # 我们需要遍历规则，看看有没有需要 AI 处理的（比如摘要、翻译）
        ai_rules = [r for r in ctx.rules if r.is_summary or r.is_ai]
        
        if not ai_rules:
            await next_call()
            return

        # 2. 提取文本内容 (如果没有文本且不是OCR场景，则跳过)
        text = ctx.message_obj.text
        if not text:
            await next_call()
            return

        # 3. 执行 AI 处理
        # 注意：这里可能很慢，但因为是 Worker 在跑，不会阻塞接收
        try:
            # 假设所有规则用同一个模型，或者取第一个配置
            # 更精细的逻辑是：针对不同规则做不同处理，这里简化为通用摘要
            model_name = ai_rules[0].ai_model or "gpt-3.5-turbo"
            prompt = ai_rules[0].ai_prompt or "请总结以下内容："
            
            provider = await get_ai_provider(model_name)
            
            # 调用 AI (假设 provider 是异步的，或者用 run_in_executor 包装)
            summary = await provider.process_message(text, prompt=prompt)
            
            # 4. 将结果挂载到 Context Metadata
            # 下游的 SenderMiddleware 可以读取这个 metadata 发送摘要
            # 同时写入通用 key 作为兜底，确保与 SenderMiddleware 所需的 modified_text 对齐
            for rule in ai_rules:
                ctx.metadata['ai_summary'] = summary
                ctx.metadata[f'modified_text_{rule.id}'] = summary
                logger.info(f"🤖 AI 处理完成 (Rule {rule.id}): {summary[:30]}...")
            
            # 写入通用 key 作为兜底
            ctx.metadata['modified_text'] = summary
            
            # 如果规则是“只发摘要”，可能需要修改 ctx.message_obj.text
            # ctx.message_obj.message = summary 
            
        except Exception as e:
            logger.error(f"AI processing failed: {e}")
            # AI 失败通常不应阻断转发，继续
            
        await next_call()
