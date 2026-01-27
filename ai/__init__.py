import logging
from .base import BaseAIProvider
from core.config.settings_loader import load_ai_models
from core.constants import DEFAULT_AI_MODEL

# 获取日志记录器
logger = logging.getLogger(__name__)

async def get_ai_provider(model=None):
    """获取AI提供者实例 (Lazy Loading)"""
    if not model:
        model = DEFAULT_AI_MODEL
    
    # 加载提供商配置（使用dict格式）
    providers_config = load_ai_models(type="dict")
    
    # 根据模型名称选择对应的提供者
    provider = None
    
    # 遍历配置中的每个提供商
    for provider_name, models_list in providers_config.items():
        # 检查完全匹配
        if model in models_list:
            try:
                if provider_name == "openai":
                    from .openai_provider import OpenAIProvider
                    provider = OpenAIProvider()
                elif provider_name == "gemini":
                    from .gemini_provider import GeminiProvider
                    provider = GeminiProvider()
                elif provider_name == "deepseek":
                    from .deepseek_provider import DeepSeekProvider
                    provider = DeepSeekProvider()
                elif provider_name == "qwen":
                    from .qwen_provider import QwenProvider
                    provider = QwenProvider()
                elif provider_name == "grok":
                    from .grok_provider import GrokProvider
                    provider = GrokProvider()
                elif provider_name == "claude":
                    from .claude_provider import ClaudeProvider
                    provider = ClaudeProvider()
            except ImportError as e:
                logger.error(f"Failed to import provider {provider_name}: {e}")
                raise ImportError(f"AI提供者 {provider_name} 不可用，请安装相关依赖")
            
            break
    
    if not provider:
        raise ValueError(f"不支持的模型: {model}")

    return provider


__all__ = [
    'BaseAIProvider',
    'get_ai_provider'
]