import logging
from typing import Any, List, Dict, Optional
from ai import get_ai_provider
from core.config import settings
from services.ai_context import AIConversationMemory, AIPromptBuilder, AITurn

logger = logging.getLogger(__name__)

class AIService:
    """AI核心业务逻辑服务"""

    def __init__(self):
        self.memory = AIConversationMemory()
        self.prompt_builder = AIPromptBuilder(self.memory)

    async def process_message(self, text: str, rule, images: List[Dict] = None, context=None) -> str:
        """调用 AI 提供商处理消息"""
        try:
            model = self._resolve_model(rule)
            prompt_template = self._resolve_prompt_template(rule)
            memory_key: Optional[str] = None
            memory_turns: List[AITurn] = []
            if settings.AI_MEMORY_ENABLED:
                self.memory.refresh_from_settings()
                memory_key = self.memory.make_key(rule, context)
                memory_turns = self.memory.snapshot(memory_key)
            
            # 1. 动态 Prompt 构建
            final_prompt = await self._build_dynamic_prompt(
                prompt_template,
                rule,
                context,
                text,
                memory_turns=memory_turns,
            )
            
            # 2. 调用 Provider
            provider = await get_ai_provider(model)
            response = await provider.process_message(
                message=text,
                prompt=final_prompt,
                model=model,
                images=images
            )
            
            # 3. 错误处理与清洗
            response_text = "" if response is None else str(response)
            if not response_text or any(x in response_text.lower() for x in ["ai处理失败", "ai failed"]):
                return text

            if memory_key:
                self.memory.append(memory_key, text, response_text)

            return response_text
            
        except Exception as e:
            logger.error(f"AI Service processing failed: {e}", exc_info=True)
            return text

    async def _build_dynamic_prompt(
        self,
        template: str,
        rule,
        context,
        message_text: str,
        memory_turns: Optional[List[AITurn]] = None,
    ) -> str:
        """构建包含聊天上下文的 Prompt"""
        return self.prompt_builder.build(template, rule, context, message_text, memory_turns)

    def _resolve_model(self, rule: Any) -> str:
        return _text_attr(rule, "ai_model") or str(getattr(settings, "DEFAULT_AI_MODEL", "gpt-4o"))

    def _resolve_prompt_template(self, rule: Any) -> str:
        if _bool_attr(rule, "is_summary"):
            return (
                _text_attr(rule, "summary_prompt")
                or _text_attr(rule, "ai_prompt")
                or str(getattr(settings, "DEFAULT_SUMMARY_PROMPT", "请总结以下内容："))
            )
        return _text_attr(rule, "ai_prompt") or str(getattr(settings, "DEFAULT_AI_PROMPT", "请总结以下内容："))


def _read_attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _text_attr(obj: Any, name: str) -> str:
    value = _read_attr(obj, name)
    if isinstance(value, (str, int, float)) and str(value):
        return str(value)
    return ""


def _bool_attr(obj: Any, name: str) -> bool:
    value = _read_attr(obj, name)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return False

ai_service = AIService()
