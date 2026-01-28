"""
转发内容增强器
为转发的消息添加智能增强功能
"""

import hashlib
from datetime import datetime

import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ContentEnhancer:
    """内容增强器"""

    def __init__(self):
        self.watermark_templates = {
            "simple": "📤 转自: {source}",
            "detailed": "📤 转自: {source}\n🕐 {time}\n#转发",
            "branded": "🔄 {bot_name} 转发\n📍 来源: {source}\n⏰ {time}",
        }

    async def enhance_message(
        self,
        message_text: str,
        source_info: Dict[str, Any],
        enhancement_config: Dict[str, Any],
    ) -> str:
        """
        增强消息内容
        """
        enhanced_text = message_text

        try:
            # 1. 添加水印
            if enhancement_config.get("add_watermark"):
                enhanced_text = await self._add_watermark(
                    enhanced_text, source_info, enhancement_config
                )

            # 2. 关键词高亮
            if enhancement_config.get("highlight_keywords"):
                enhanced_text = await self._highlight_keywords(
                    enhanced_text, enhancement_config.get("keywords", [])
                )

            # 3. 添加标签
            if enhancement_config.get("add_tags"):
                enhanced_text = await self._add_tags(
                    enhanced_text, enhancement_config.get("tags", [])
                )

            # 4. 链接预处理
            if enhancement_config.get("process_links"):
                enhanced_text = await self._process_links(enhanced_text)

            # 5. 格式美化
            if enhancement_config.get("beautify_format"):
                enhanced_text = await self._beautify_format(enhanced_text)

            # 6. 添加统计信息
            if enhancement_config.get("add_stats"):
                enhanced_text = await self._add_stats(enhanced_text, source_info)

            return enhanced_text

        except Exception as e:
            logger.error(f"内容增强失败: {e}")
            return message_text  # 返回原始内容

    async def _add_watermark(
        self, text: str, source_info: Dict[str, Any], config: Dict[str, Any]
    ) -> str:
        """添加水印"""
        watermark_style = config.get("watermark_style", "simple")
        template = self.watermark_templates.get(
            watermark_style, self.watermark_templates["simple"]
        )

        watermark = template.format(
            source=source_info.get("source_name", "未知来源"),
            time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            bot_name=config.get("bot_name", "TelegramForwarder"),
        )

        position = config.get("watermark_position", "bottom")
        if position == "top":
            return f"{watermark}\n\n{text}"
        else:
            return f"{text}\n\n{watermark}"

    async def _highlight_keywords(self, text: str, keywords: list) -> str:
        """关键词高亮"""
        for keyword in keywords:
            # 使用 Markdown 粗体高亮
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            text = pattern.sub(f"**{keyword}**", text)
        return text

    async def _add_tags(self, text: str, tags: list) -> str:
        """添加标签"""
        if tags:
            tag_text = " ".join([f"#{tag}" for tag in tags])
            return f"{text}\n\n{tag_text}"
        return text

    async def _process_links(self, text: str) -> str:
        """处理链接"""
        # 短链接展开、危险链接警告等
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

        def process_url(match):
            url = match.group(0)
            # 这里可以添加链接安全检查、短链接展开等逻辑
            return f"🔗 {url}"

        return re.sub(url_pattern, process_url, text)

    async def _beautify_format(self, text: str) -> str:
        """格式美化"""
        # 添加适当的换行、缩进等
        lines = text.split("\n")
        beautified_lines = []

        for line in lines:
            line = line.strip()
            if line:
                # 为标题添加装饰
                if line.isupper() and len(line) < 50:
                    line = f"✨ **{line}** ✨"
                beautified_lines.append(line)
            else:
                beautified_lines.append("")

        return "\n".join(beautified_lines)

    async def _add_stats(self, text: str, source_info: Dict[str, Any]) -> str:
        """添加统计信息"""
        stats = []

        # 字符统计
        char_count = len(text)
        if char_count > 100:
            stats.append(f"📊 字符数: {char_count}")

        # 链接统计
        url_count = len(re.findall(r"http[s]?://\S+", text))
        if url_count > 0:
            stats.append(f"🔗 链接数: {url_count}")

        # 提及统计
        mention_count = len(re.findall(r"@\w+", text))
        if mention_count > 0:
            stats.append(f"👤 提及数: {mention_count}")

        if stats:
            stats_text = " | ".join(stats)
            return f"{text}\n\n📈 {stats_text}"

        return text

    async def generate_summary(self, text: str, max_length: int = 100) -> str:
        """生成内容摘要"""
        if len(text) <= max_length:
            return text

        # 简单的摘要算法：取前几句话
        sentences = re.split(r"[.!?。！？]", text)
        summary = ""

        for sentence in sentences:
            if len(summary + sentence) <= max_length - 3:
                summary += sentence + "。"
            else:
                break

        return summary + "..." if summary else text[: max_length - 3] + "..."

    def calculate_content_hash(self, text: str) -> str:
        """计算内容哈希（用于相似内容检测）"""
        # 移除格式字符，计算内容哈希
        clean_text = re.sub(r"[^\w\s]", "", text.lower())
        return hashlib.md5(clean_text.encode()).hexdigest()


# 提示：该模块当前未在项目中直接引用。
# 如需启用，请从调用方导入 ContentEnhancer 并按需实例化。
