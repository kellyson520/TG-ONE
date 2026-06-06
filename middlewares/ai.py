from core.pipeline import Middleware, MessageContext
from services.ai_service import ai_service
import logging

logger = logging.getLogger(__name__)

class AIMiddleware(Middleware):
    def __init__(self, service=None):
        self.ai_service = service or ai_service

    async def process(self, ctx: MessageContext, next_call):
        # 1. 检查是否有规则启用了 AI
        # 遍历规则，找出需要 AI 处理的（摘要、翻译、重写等）。
        ai_rules = [r for r in ctx.rules if _rule_flag(r, "is_summary") or _rule_flag(r, "is_ai")]
        
        if not ai_rules:
            await next_call()
            return

        # 2. 提取文本内容 (如果没有文本且不是OCR场景，则跳过)
        text = _message_text(ctx.message_obj)
        if not text:
            await next_call()
            return

        # 3. 执行 AI 处理
        # 注意：这里可能很慢，但因为是 Worker 在跑，不会阻塞接收
        first_modified_text = None
        try:
            for rule in ai_rules:
                rule_text = _rule_text(ctx, rule, text)
                result = await self.ai_service.process_message(rule_text, rule, context=ctx)
                if not result or result == rule_text:
                    logger.info(f"🤖 AI 未产生变更，保留原文 (Rule {getattr(rule, 'id', 'unknown')})")
                    continue

                rule_id = getattr(rule, "id", None)
                if rule_id is not None:
                    ctx.metadata[f"modified_text_{rule_id}"] = result
                if _rule_flag(rule, "is_summary"):
                    ctx.metadata["ai_summary"] = result
                if first_modified_text is None:
                    first_modified_text = result
                logger.info(f"🤖 AI 处理完成 (Rule {rule_id or 'unknown'}): {result[:30]}...")

            # 只有全部剩余规则都走 AI 时才写全局兜底，避免污染同源普通转发规则。
            if first_modified_text and len(ai_rules) == len(ctx.rules):
                ctx.metadata["modified_text"] = first_modified_text
            
        except Exception as e:
            logger.error(f"AI processing failed: {e}", exc_info=True)
            # AI 失败通常不应阻断转发，继续
            
        await next_call()


def _message_text(message_obj) -> str:
    text = getattr(message_obj, "text", None)
    if text:
        return str(text)
    message = getattr(message_obj, "message", None)
    return str(message) if message else ""


def _rule_text(ctx: MessageContext, rule, original_text: str) -> str:
    rule_id = getattr(rule, "id", None)
    if rule_id is not None:
        modified = ctx.metadata.get(f"modified_text_{rule_id}")
        if modified:
            return str(modified)
    modified = ctx.metadata.get("modified_text")
    return str(modified) if modified else original_text


def _rule_flag(rule, name: str) -> bool:
    value = getattr(rule, name, False)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return False
