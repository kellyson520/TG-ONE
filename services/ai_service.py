import logging
from typing import List, Dict, Optional
from ai import get_ai_provider
from core.config import settings
from core.constants import DEFAULT_AI_MODEL, DEFAULT_AI_PROMPT
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
            model = rule.ai_model or DEFAULT_AI_MODEL
            prompt_template = rule.ai_prompt or DEFAULT_AI_PROMPT
            memory_key: Optional[str] = None
            memory_turns: List[AITurn] = []
            if settings.AI_MEMORY_ENABLED:
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
            if not response or any(x in str(response).lower() for x in ["ai处理失败", "ai failed"]):
                return text

            if memory_key:
                self.memory.append(memory_key, text, response)

            return response
            
        except Exception as e:
            logger.error(f"AI Service processing failed: {e}")
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

ai_service = AIService()
