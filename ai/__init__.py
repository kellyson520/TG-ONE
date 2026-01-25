from .base import BaseAIProvider

# 可选导入AI提供者，避免缺少依赖时报错
try:
    from .openai_provider import OpenAIProvider
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAIProvider = None
    OPENAI_AVAILABLE = False

try:
    from .gemini_provider import GeminiProvider
    GEMINI_AVAILABLE = True
except ImportError:
    GeminiProvider = None
    GEMINI_AVAILABLE = False

try:
    from .deepseek_provider import DeepSeekProvider
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DeepSeekProvider = None
    DEEPSEEK_AVAILABLE = False

try:
    from .qwen_provider import QwenProvider
    QWEN_AVAILABLE = True
except ImportError:
    QwenProvider = None
    QWEN_AVAILABLE = False

try:
    from .grok_provider import GrokProvider
    GROK_AVAILABLE = True
except ImportError:
    GrokProvider = None
    GROK_AVAILABLE = False

try:
    from .claude_provider import ClaudeProvider
    CLAUDE_AVAILABLE = True
except ImportError:
    ClaudeProvider = None
    CLAUDE_AVAILABLE = False
import os
import logging
from utils.core.settings import load_ai_models
from utils.core.constants import DEFAULT_AI_MODEL

# 获取日志记录器
logger = logging.getLogger(__name__)

async def get_ai_provider(model=None):
    """获取AI提供者实例"""
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
            if provider_name == "openai" and OPENAI_AVAILABLE:
                provider = OpenAIProvider()
            elif provider_name == "gemini" and GEMINI_AVAILABLE:
                provider = GeminiProvider()
            elif provider_name == "deepseek" and DEEPSEEK_AVAILABLE:
                provider = DeepSeekProvider()
            elif provider_name == "qwen" and QWEN_AVAILABLE:
                provider = QwenProvider()
            elif provider_name == "grok" and GROK_AVAILABLE:
                provider = GrokProvider()
            elif provider_name == "claude" and CLAUDE_AVAILABLE:
                provider = ClaudeProvider()
            elif provider_name in ["openai", "gemini", "deepseek", "qwen", "grok", "claude"]:
                # 提供者不可用的情况
                raise ImportError(f"AI提供者 {provider_name} 不可用，请安装相关依赖")
            break
    
    if not provider:
        raise ValueError(f"不支持的模型: {model}")

    return provider


__all__ = [
    'BaseAIProvider',
    'get_ai_provider'
]

# 只导出可用的提供者
if OPENAI_AVAILABLE:
    __all__.append('OpenAIProvider')
if GEMINI_AVAILABLE:
    __all__.append('GeminiProvider')
if DEEPSEEK_AVAILABLE:
    __all__.append('DeepSeekProvider')
if QWEN_AVAILABLE:
    __all__.append('QwenProvider')
if GROK_AVAILABLE:
    __all__.append('GrokProvider')
if CLAUDE_AVAILABLE:
    __all__.append('ClaudeProvider')