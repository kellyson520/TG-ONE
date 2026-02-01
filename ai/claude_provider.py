from typing import Optional, List, Dict
from core.helpers.lazy_import import LazyImport

anthropic = LazyImport("anthropic")
# import anthropic (Moved to local scope)
from ai.base import BaseAIProvider
from core.config import settings
import logging

logger = logging.getLogger(__name__)

class ClaudeProvider(BaseAIProvider):
    def __init__(self):
        self.client = None
        self.model = None
        self.default_model = 'claude-3-5-sonnet-latest'
        
    async def initialize(self, **kwargs):
        """初始化Claude客户端"""
        api_key = settings.CLAUDE_API_KEY
        if not api_key:
            raise ValueError("未设置 CLAUDE_API_KEY")
            
        # 检查是否配置了自定义API基础URL
        api_base = (settings.CLAUDE_API_BASE or '').strip()
        if api_base:
            logger.info(f"使用自定义Claude API基础URL: {api_base}")
            self.client = anthropic.Anthropic(
                api_key=api_key,
                base_url=api_base
            )
        else:
            # 使用默认URL
            self.client = anthropic.Anthropic(api_key=api_key)
            
        self.model = kwargs.get('model', self.default_model)
        
    async def process_message(self, 
                            message: str, 
                            prompt: Optional[str] = None,
                            images: Optional[List[Dict[str, str]]] = None,
                            **kwargs) -> str:
        """处理消息"""
        try:
            if not self.client:
                await self.initialize(**kwargs)
                
            # 构建消息列表
            messages = []
            if prompt:
                messages.append({"role": "system", "content": prompt})
            
            # 如果有图片，需要添加到消息中
            if images and len(images) > 0:
                # 构建包含图片的内容列表
                content = []
                
                # 添加文本
                content.append({
                    "type": "text",
                    "text": message
                })
                
                # 添加每张图片
                for img in images:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": img["mime_type"],
                            "data": img["data"]
                        }
                    })
                    logger.info(f"已添加一张类型为 {img['mime_type']} 的图片，大小约 {len(img['data']) // 1000} KB")
                
                # 添加用户消息
                messages.append({"role": "user", "content": content})
            else:
                # 没有图片，只添加文本
                messages.append({"role": "user", "content": message})
            
            # 使用流式输出 - 按照官方文档正确实现
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                messages=messages
            ) as stream:
                # 使用专用的text_stream迭代器直接获取文本
                full_response = ""
                for text in stream.text_stream:
                    full_response += text
        
            return full_response
            
        except Exception as e:
            logger.error(f"Claude API 调用失败: {str(e)}")
            return f"AI处理失败: {str(e)}" 