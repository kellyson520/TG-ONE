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

    # Wrap provider with Circuit Breaker Proxy
    from core.helpers.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException
    
    # Store breakers in a static dict within the function or module scope
    if not hasattr(get_ai_provider, "breakers"):
        get_ai_provider.breakers = {}
        
    cb_key = f"ai_provider_{model}"
    if cb_key not in get_ai_provider.breakers:
        # P1 Requirement: 5 failures, 60s recovery (aggressive protection)
        get_ai_provider.breakers[cb_key] = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
    
    cb = get_ai_provider.breakers[cb_key]

    # Create a proxy wrapper
    class CircuitBreakerProxy:
        def __init__(self, target, breaker):
            self._target = target
            self._breaker = breaker
            
        async def process_message(self, *args, **kwargs):
            async def _call():
                return await self._target.process_message(*args, **kwargs)
            
            try:
                return await self._breaker.call(_call)
            except CircuitBreakerOpenException:
                logger.warning(f"AI Provider {model} is circuit broken. Downgrading...")
                # Fallback logic: return empty string or specific marker to skip AI
                # The caller (AIMiddleware) should handle empty response
                return ""
            except Exception as e:
                # Rethrow other exceptions so CB counts them
                raise e
                
        def __getattr__(self, name):
            return getattr(self._target, name)

    return CircuitBreakerProxy(provider, cb)


__all__ = [
    'BaseAIProvider',
    'get_ai_provider'
]