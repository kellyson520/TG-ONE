"""
搜索界面管理器
负责生成搜索结果的统一界面，包括分页、筛选、排序等交互功能
"""

from telethon import Button
from typing import Any, Dict, List, Optional, Tuple

from utils.core.logger_utils import get_logger
from utils.helpers.search_system import (
    SearchFilter,
    SearchResponse,
    SearchResult,
    SearchType,
    SortBy,
)

logger = get_logger(__name__)


class SearchUIManager:
    """搜索界面管理器"""

    # 表情符号映射
    TYPE_EMOJIS = {
        "bound_chat": "📌",
        "public_chat": "🌐",
        "channel": "📢",
        "supergroup": "🏢",
        "group": "👥",
        "private": "👤",
        "message": "💬",
        "video": "🎬",
        "image": "🖼️",
        "file": "📁",
        "link": "🔗",
    }

    SORT_EMOJIS = {
        SortBy.TIME_DESC: "🕐⬇️",
        SortBy.TIME_ASC: "🕐⬆️",
        SortBy.SIZE_DESC: "📏⬇️",
        SortBy.SIZE_ASC: "📏⬆️",
        SortBy.RELEVANCE: "🎯",
        SortBy.MEMBERS: "👥",
        SortBy.ACTIVITY: "🔥",
    }

    SORT_NAMES = {
        SortBy.TIME_DESC: "时间↓",
        SortBy.TIME_ASC: "时间↑",
        SortBy.SIZE_DESC: "大小↓",
        SortBy.SIZE_ASC: "大小↑",
        SortBy.RELEVANCE: "相关性",
        SortBy.MEMBERS: "成员数",
        SortBy.ACTIVITY: "活跃度",
    }

    @staticmethod
    def generate_search_message(response: SearchResponse) -> str:
        """生成搜索结果消息"""
        if not response.results:
            return f'🔍 未找到包含 "{response.query}" 的结果'

        # 消息头部
        cache_indicator = " 📦" if response.cached else ""
        header = (
            f"🔍 搜索结果{cache_indicator}\n"
            f'📝 关键词: "{response.query}"\n'
            f"📊 共 {response.total_count} 个结果，第 {response.current_page}/{response.total_pages} 页\n"
            f"⏱️ 用时 {response.search_time:.2f}s\n"
        )

        # 筛选器信息
        filter_info = SearchUIManager._generate_filter_info(response.filters)
        if filter_info:
            header += f"🎛️ {filter_info}\n"

        header += "\n"

        # 结果列表
        results_text = ""
        for i, result in enumerate(response.results, 1):
            emoji = SearchUIManager.TYPE_EMOJIS.get(result.type, "💬")

            # 构建结果项
            result_line = f"{emoji} <b>{i}. {result.title}</b>\n"

            # 添加描述
            if result.description:
                result_line += f"   {result.description}\n"

            # 添加额外信息
            info_parts = []
            if result.members > 0:
                info_parts.append(f"👥 {result.members}")
            if result.size > 0:
                size_mb = result.size / (1024 * 1024)
                if size_mb >= 1:
                    info_parts.append(f"📏 {size_mb:.1f}MB")
                else:
                    size_kb = result.size / 1024
                    info_parts.append(f"📏 {size_kb:.1f}KB")
            if result.activity_score > 0:
                info_parts.append(f"🔥 {result.activity_score:.1f}")

            if info_parts:
                result_line += f"   {' | '.join(info_parts)}\n"

            # 添加链接
            if result.link:
                result_line += f"   🔗 {result.link}\n"

            result_line += "\n"
            results_text += result_line

        return header + results_text

    @staticmethod
    def _generate_filter_info(filters: SearchFilter) -> str:
        """生成筛选器信息字符串"""
        info_parts = []

        # 搜索类型
        if filters.search_type != SearchType.ALL:
            type_name = {
                SearchType.BOUND_CHATS: "已绑定",
                SearchType.PUBLIC_CHATS: "公开群组",
                SearchType.MESSAGES: "消息",
                SearchType.VIDEOS: "视频",
                SearchType.IMAGES: "图片",
                SearchType.FILES: "文件",
                SearchType.LINKS: "链接",
                SearchType.CHANNELS: "频道",
                SearchType.GROUPS: "群组",
            }.get(filters.search_type, "未知")
            info_parts.append(f"类型:{type_name}")

        # 排序方式
        if filters.sort_by != SortBy.RELEVANCE:
            sort_name = SearchUIManager.SORT_NAMES.get(filters.sort_by, "未知")
            info_parts.append(f"排序:{sort_name}")

        # 聊天类型筛选
        if filters.chat_types:
            chat_types_str = ",".join(filters.chat_types)
            info_parts.append(f"聊天:{chat_types_str}")

        # 媒体类型筛选
        if filters.media_types:
            media_types_str = ",".join(filters.media_types)
            info_parts.append(f"媒体:{media_types_str}")

        return " | ".join(info_parts)

    @staticmethod
    def generate_pagination_buttons(
        response: SearchResponse, callback_prefix: str
    ) -> List[List[Button]]:
        """生成分页按钮"""
        buttons = []

        # 第一行：筛选和排序按钮
        filter_sort_row = []

        # 类型筛选按钮
        filter_sort_row.append(
            Button.inline(f"🎛️ 筛选", f"{callback_prefix}_filter:{response.query}")
        )

        # 排序按钮
        sort_emoji = SearchUIManager.SORT_EMOJIS.get(response.filters.sort_by, "🎯")
        filter_sort_row.append(
            Button.inline(
                f"{sort_emoji} 排序", f"{callback_prefix}_sort:{response.query}"
            )
        )

        buttons.append(filter_sort_row)

        # 第二行：分页按钮
        if response.total_pages > 1:
            nav_row = []

            # 首页按钮
            if response.current_page > 1:
                nav_row.append(
                    Button.inline(
                        "⏮️ 首页", f"{callback_prefix}_page:1:{response.query}"
                    )
                )

            # 上一页按钮
            if response.current_page > 1:
                nav_row.append(
                    Button.inline(
                        "⬅️ 上页",
                        f"{callback_prefix}_page:{response.current_page - 1}:{response.query}",
                    )
                )

            # 页码信息
            nav_row.append(
                Button.inline(
                    f"📄 {response.current_page}/{response.total_pages}",
                    f"{callback_prefix}_info",
                )
            )

            # 下一页按钮
            if response.current_page < response.total_pages:
                nav_row.append(
                    Button.inline(
                        "➡️ 下页",
                        f"{callback_prefix}_page:{response.current_page + 1}:{response.query}",
                    )
                )

            # 末页按钮
            if response.current_page < response.total_pages:
                nav_row.append(
                    Button.inline(
                        "⏭️ 末页",
                        f"{callback_prefix}_page:{response.total_pages}:{response.query}",
                    )
                )

            buttons.append(nav_row)

        # 第三行：操作按钮
        action_row = []

        # 刷新按钮
        action_row.append(
            Button.inline("🔄 刷新", f"{callback_prefix}_refresh:{response.query}")
        )

        # 新搜索按钮
        action_row.append(Button.inline("🆕 新搜索", f"{callback_prefix}_new"))

        buttons.append(action_row)

        return buttons

    @staticmethod
    def generate_filter_buttons(
        current_filters: SearchFilter, callback_prefix: str, query: str
    ) -> List[List[Button]]:
        """生成筛选器按钮"""
        buttons = []

        # 搜索类型选择
        type_row1 = []
        type_row2 = []

        type_buttons = [
            (SearchType.ALL, "🔍 全部"),
            (SearchType.BOUND_CHATS, "📌 已绑定"),
            (SearchType.PUBLIC_CHATS, "🌐 公开"),
            (SearchType.CHANNELS, "📢 频道"),
            (SearchType.GROUPS, "👥 群组"),
            (SearchType.MESSAGES, "💬 消息"),
            (SearchType.VIDEOS, "🎬 视频"),
            (SearchType.IMAGES, "🖼️ 图片"),
            (SearchType.FILES, "📁 文件"),
            (SearchType.LINKS, "🔗 链接"),
        ]

        for i, (search_type, label) in enumerate(type_buttons):
            # 当前选中的类型加上 ✅
            if current_filters.search_type == search_type:
                label = f"✅ {label}"

            button = Button.inline(
                label, f"{callback_prefix}_set_type:{search_type.value}:{query}"
            )

            if i < 5:
                type_row1.append(button)
            else:
                type_row2.append(button)

        buttons.extend([type_row1, type_row2])

        # 聊天类型筛选（仅在相关搜索类型时显示）
        if current_filters.search_type in [
            SearchType.ALL,
            SearchType.BOUND_CHATS,
            SearchType.PUBLIC_CHATS,
            SearchType.CHANNELS,
            SearchType.GROUPS,
        ]:
            chat_type_row = []
            chat_types = ["channel", "supergroup", "group", "private"]

            for chat_type in chat_types:
                emoji_map = {
                    "channel": "📢",
                    "supergroup": "🏢",
                    "group": "👥",
                    "private": "👤",
                }
                emoji = emoji_map.get(chat_type, "💬")

                # 检查是否已选中
                if chat_type in current_filters.chat_types:
                    label = f"✅ {emoji}"
                else:
                    label = emoji

                chat_type_row.append(
                    Button.inline(
                        label, f"{callback_prefix}_toggle_chat_type:{chat_type}:{query}"
                    )
                )

            buttons.append(chat_type_row)

        # 返回和应用按钮
        control_row = []
        control_row.append(Button.inline("🔙 返回", f"{callback_prefix}_back:{query}"))
        control_row.append(Button.inline("✅ 应用", f"{callback_prefix}_apply:{query}"))
        buttons.append(control_row)

        return buttons

    @staticmethod
    def generate_sort_buttons(
        current_filters: SearchFilter, callback_prefix: str, query: str
    ) -> List[List[Button]]:
        """生成排序按钮"""
        buttons = []

        sort_options = [
            (SortBy.RELEVANCE, "🎯 相关性"),
            (SortBy.TIME_DESC, "🕐⬇️ 最新"),
            (SortBy.TIME_ASC, "🕐⬆️ 最旧"),
            (SortBy.MEMBERS, "👥 成员数"),
            (SortBy.ACTIVITY, "🔥 活跃度"),
            (SortBy.SIZE_DESC, "📏⬇️ 大到小"),
            (SortBy.SIZE_ASC, "📏⬆️ 小到大"),
        ]

        # 分成两行显示
        row1 = []
        row2 = []

        for i, (sort_by, label) in enumerate(sort_options):
            # 当前选中的排序方式加上 ✅
            if current_filters.sort_by == sort_by:
                label = f"✅ {label}"

            button = Button.inline(
                label, f"{callback_prefix}_set_sort:{sort_by.value}:{query}"
            )

            if i < 4:
                row1.append(button)
            else:
                row2.append(button)

        buttons.extend([row1, row2])

        # 返回按钮
        control_row = [Button.inline("🔙 返回", f"{callback_prefix}_back:{query}")]
        buttons.append(control_row)

        return buttons

    @staticmethod
    def generate_result_detail_buttons(
        result: SearchResult, callback_prefix: str
    ) -> List[List[Button]]:
        """生成结果详情按钮"""
        buttons = []

        # 操作按钮行
        action_row = []

        # 如果是聊天类型，添加绑定按钮
        if result.type in ["bound_chat", "public_chat"]:
            action_row.append(
                Button.inline("🔗 绑定", f"{callback_prefix}_bind:{result.telegram_id}")
            )

        # 如果有链接，添加打开链接按钮
        if result.link:
            action_row.append(Button.url("🔗 打开", result.link))

        # 查看详情按钮
        action_row.append(
            Button.inline("📋 详情", f"{callback_prefix}_detail:{result.id}")
        )

        if action_row:
            buttons.append(action_row)

        # 返回按钮
        back_row = [Button.inline("🔙 返回搜索", f"{callback_prefix}_back")]
        buttons.append(back_row)

        return buttons
