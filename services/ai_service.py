
import logging
import re
from typing import List, Dict, Optional, Any
from ai import get_ai_provider
from core.constants import DEFAULT_AI_MODEL, DEFAULT_AI_PROMPT
from core.helpers.id_utils import resolve_entity_by_id_variants
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AIService:
    """AI核心业务逻辑服务"""

    async def process_message(self, text: str, rule, images: List[Dict] = None, context=None) -> str:
        """调用 AI 提供商处理消息"""
        try:
            model = rule.ai_model or DEFAULT_AI_MODEL
            prompt_template = rule.ai_prompt or DEFAULT_AI_PROMPT
            
            # 1. 动态 Prompt 构建
            final_prompt = await self._build_dynamic_prompt(prompt_template, rule, context, text)
            
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
                
            return response
            
        except Exception as e:
            logger.error(f"AI Service processing failed: {e}")
            return text

    async def _build_dynamic_prompt(self, template: str, rule, context, message_text: str) -> str:
        """构建包含聊天上下文的 Prompt"""
        prompt = template
        
        # 简单替换
        if '{Message}' in prompt:
            prompt = prompt.replace('{Message}', message_text)
            
        # 复杂上下文提取 (Source/Target Context/Time)
        # 此处简化实现，完整实现需引入 API Optimizer 或 Client
        if "{" in prompt and getattr(context, 'client', None):
             # TODO: 完整迁移 _get_chat_messages 及其正则解析逻辑
             # 为保持本次重构的原子性，暂时保留基础替换
             pass

        return prompt

ai_service = AIService()
