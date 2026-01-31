"""
媒体筛选器
根据全局媒体设置筛选消息
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MediaFilter:
    """媒体筛选器 - 根据设置判断是否处理消息"""

    def __init__(self, media_settings: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化媒体筛选器

        Args:
            media_settings: 媒体设置字典
        """
        self.media_settings = media_settings or self._get_default_settings()

        # 统计信息
        self.total_checked = 0
        self.total_allowed = 0
        self.total_filtered = 0
        self.filter_reasons: Dict[str, int] = {}

    @staticmethod
    def _get_default_settings() -> Dict[str, Any]:
        """获取默认媒体设置"""
        return {
            "allow_text": True,
            "media_types": {
                "image": True,
                "video": True,
                "audio": True,
                "voice": True,
                "document": True,
            },
            "duration_limits": {
                "min_duration": 0,  # 秒
                "max_duration": float("inf"),  # 无限制
            },
        }

    def update_settings(self, media_settings: Dict[str, Any]) -> None:
        """更新媒体设置"""
        self.media_settings = media_settings

    async def should_process_message(self, message: Any) -> tuple[bool, Optional[str]]:
        """
        判断是否应该处理消息

        Args:
            message: Telethon消息对象

        Returns:
            tuple[bool, Optional[str]]: (是否处理, 过滤原因)
        """
        self.total_checked += 1

        # 1. 检查文本消息
        if not message.media:
            allowed = self.media_settings.get("allow_text", True)
            if not allowed:
                self.total_filtered += 1
                self._record_filter_reason("text_disabled")
                return False, "文本消息已禁用"

            self.total_allowed += 1
            return True, None

        # 2. 检查媒体类型
        media_type = self._get_media_type(message)
        if not media_type:
            # 未知媒体类型，默认允许
            self.total_allowed += 1
            return True, None

        media_types = self.media_settings.get("media_types", {})
        if not media_types.get(media_type, True):
            self.total_filtered += 1
            self._record_filter_reason(f"{media_type}_disabled")
            return False, f"{media_type}类型已禁用"

        # 3. 检查媒体时长
        if media_type in ["video", "audio", "voice"]:
            duration_ok, reason = self._check_duration(message)
            if not duration_ok:
                self.total_filtered += 1
                self._record_filter_reason("duration_limit")
                return False, reason

        self.total_allowed += 1
        return True, None

    def _get_media_type(self, message: Any) -> Optional[str]:
        """
        获取消息的媒体类型

        Args:
            message: Telethon消息对象

        Returns:
            Optional[str]: 媒体类型名称
        """
        if message.photo:
            return "image"
        elif message.video:
            return "video"
        elif message.audio:
            return "audio"
        elif message.voice:
            return "voice"
        elif message.document:
            return "document"
        return None

    def _check_duration(self, message: Any) -> tuple[bool, Optional[str]]:
        """
        检查媒体时长是否符合要求

        Args:
            message: Telethon消息对象

        Returns:
            tuple[bool, Optional[str]]: (是否符合, 原因)
        """
        # 获取媒体对象
        media = message.media
        if not media:
            return True, None

        # 尝试获取时长
        duration = None
        if hasattr(media, "document") and media.document:
            # 从document attributes中获取时长
            for attr in getattr(media.document, "attributes", []):
                if hasattr(attr, "duration"):
                    duration = attr.duration
                    break

        if duration is None:
            # 无法获取时长，默认允许
            return True, None

        # 检查时长限制
        duration_limits = self.media_settings.get("duration_limits", {})
        min_duration = duration_limits.get("min_duration", 0)
        max_duration = duration_limits.get("max_duration", float("inf"))

        if duration < min_duration:
            return False, f"时长{duration}秒 < 最小限制{min_duration}秒"

        if duration > max_duration:
            return False, f"时长{duration}秒 > 最大限制{max_duration}秒"

        return True, None

    def _record_filter_reason(self, reason: str) -> None:
        """记录过滤原因统计"""
        self.filter_reasons[reason] = self.filter_reasons.get(reason, 0) + 1

    def get_statistics(self) -> Dict[str, Any]:
        """获取筛选统计信息"""
        return {
            "total_checked": self.total_checked,
            "total_allowed": self.total_allowed,
            "total_filtered": self.total_filtered,
            "filter_rate": (
                round(self.total_filtered / self.total_checked * 100, 2)
                if self.total_checked > 0
                else 0
            ),
            "filter_reasons": self.filter_reasons.copy(),
        }

    def reset_statistics(self) -> None:
        """重置统计信息"""
        self.total_checked = 0
        self.total_allowed = 0
        self.total_filtered = 0
        self.filter_reasons.clear()

    def __repr__(self) -> str:
        return (
            f"<MediaFilter "
            f"checked={self.total_checked} "
            f"allowed={self.total_allowed} "
            f"filtered={self.total_filtered}>"
        )
