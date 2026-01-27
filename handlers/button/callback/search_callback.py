"""
搜索回调处理器
处理搜索相关的按钮回调事件
"""

import json
from telethon import events
from typing import Any, Dict

from handlers.search_ui_manager import SearchUIManager
from core.helpers.auto_delete import respond_and_delete
from core.helpers.common import get_user_client
from core.logging import get_logger
from core.helpers.search_system import SearchFilter, SearchType, SortBy, get_search_system

logger = get_logger(__name__)


class SearchCallbackHandler:
    """搜索回调处理器"""

    def __init__(self):
        self.user_filters: Dict[int, SearchFilter] = {}  # 存储用户的筛选器状态

    async def handle_search_callback(self, event: events.CallbackQuery):
        """处理搜索相关回调"""
        try:
            callback_data = event.data.decode("utf-8")
            logger.debug(f"搜索回调数据: {callback_data}")

            # 解析回调数据
            if not callback_data.startswith("search_"):
                return False

            parts = callback_data.split(":", 2)
            if len(parts) < 2:
                return False

            action = parts[0]  # search_page, search_filter, search_sort 等
            operation = parts[1]  # 具体操作

            # 获取用户ID
            user_id = event.sender_id

            # 初始化用户筛选器
            if user_id not in self.user_filters:
                self.user_filters[user_id] = SearchFilter()

            # 根据操作类型分发处理
            if action == "search_page":
                await self._handle_page_change(
                    event, operation, parts[2] if len(parts) > 2 else ""
                )
            elif action == "search_filter":
                await self._handle_filter_menu(event, operation)
            elif action == "search_sort":
                await self._handle_sort_menu(event, operation)
            elif action == "search_set_type":
                await self._handle_set_search_type(
                    event, operation, parts[2] if len(parts) > 2 else ""
                )
            elif action == "search_set_sort":
                await self._handle_set_sort(
                    event, operation, parts[2] if len(parts) > 2 else ""
                )
            elif action == "search_toggle_chat_type":
                await self._handle_toggle_chat_type(
                    event, operation, parts[2] if len(parts) > 2 else ""
                )
            elif action == "search_apply":
                await self._handle_apply_filters(event, operation)
            elif action == "search_back":
                await self._handle_back_to_search(event, operation)
            elif action == "search_refresh":
                await self._handle_refresh_search(event, operation)
            elif action == "search_new":
                await self._handle_new_search(event)
            elif action == "search_bind":
                await self._handle_bind_chat(event, operation)
            elif action == "search_detail":
                await self._handle_show_detail(event, operation)
            else:
                logger.warning(f"未知的搜索回调操作: {action}")
                return False

            return True

        except Exception as e:
            logger.error(f"处理搜索回调失败: {e}")
            await event.answer("❌ 操作失败", alert=True)
            return False

    async def _handle_page_change(
        self, event: events.CallbackQuery, page_str: str, query: str
    ):
        """处理分页变更"""
        try:
            page = int(page_str)
            user_id = event.sender_id
            filters = self.user_filters.get(user_id, SearchFilter())

            # 执行搜索（正确获取异步客户端）
            user_client = await get_user_client()
            search_system = get_search_system(user_client)
            response = await search_system.search(query, filters, page)

            # 生成界面
            message_text = SearchUIManager.generate_search_message(response)
            buttons = SearchUIManager.generate_pagination_buttons(response, "search")

            await event.edit(message_text, buttons=buttons, parse_mode="HTML")
            await event.answer()

        except ValueError:
            await event.answer("❌ 页码错误", alert=True)
        except Exception as e:
            logger.error(f"处理分页失败: {e}")
            await event.answer("❌ 分页失败", alert=True)

    async def _handle_filter_menu(self, event: events.CallbackQuery, query: str):
        """处理筛选器菜单"""
        try:
            user_id = event.sender_id
            filters = self.user_filters.get(user_id, SearchFilter())

            # 生成筛选器界面
            message_text = (
                f"🎛️ <b>搜索筛选器</b>\n"
                f'关键词: "{query}"\n\n'
                f"请选择要筛选的内容类型和条件："
            )

            buttons = SearchUIManager.generate_filter_buttons(filters, "search", query)

            await event.edit(message_text, buttons=buttons, parse_mode="HTML")
            await event.answer()

        except Exception as e:
            logger.error(f"处理筛选器菜单失败: {e}")
            await event.answer("❌ 筛选器菜单失败", alert=True)

    async def _handle_sort_menu(self, event: events.CallbackQuery, query: str):
        """处理排序菜单"""
        try:
            user_id = event.sender_id
            filters = self.user_filters.get(user_id, SearchFilter())

            # 生成排序界面
            message_text = (
                f"🔄 <b>搜索排序</b>\n" f'关键词: "{query}"\n\n' f"请选择排序方式："
            )

            buttons = SearchUIManager.generate_sort_buttons(filters, "search", query)

            await event.edit(message_text, buttons=buttons, parse_mode="HTML")
            await event.answer()

        except Exception as e:
            logger.error(f"处理排序菜单失败: {e}")
            await event.answer("❌ 排序菜单失败", alert=True)

    async def _handle_set_search_type(
        self, event: events.CallbackQuery, type_str: str, query: str
    ):
        """处理设置搜索类型"""
        try:
            user_id = event.sender_id
            search_type = SearchType(type_str)

            # 更新用户筛选器
            if user_id not in self.user_filters:
                self.user_filters[user_id] = SearchFilter()

            self.user_filters[user_id].search_type = search_type

            # 重新生成筛选器界面
            await self._handle_filter_menu(event, query)

        except ValueError:
            await event.answer("❌ 搜索类型错误", alert=True)
        except Exception as e:
            logger.error(f"设置搜索类型失败: {e}")
            await event.answer("❌ 设置失败", alert=True)

    async def _handle_set_sort(
        self, event: events.CallbackQuery, sort_str: str, query: str
    ):
        """处理设置排序方式"""
        try:
            user_id = event.sender_id
            sort_by = SortBy(sort_str)

            # 更新用户筛选器
            if user_id not in self.user_filters:
                self.user_filters[user_id] = SearchFilter()

            self.user_filters[user_id].sort_by = sort_by

            # 立即应用新的排序方式
            await self._handle_apply_filters(event, query)

        except ValueError:
            await event.answer("❌ 排序方式错误", alert=True)
        except Exception as e:
            logger.error(f"设置排序方式失败: {e}")
            await event.answer("❌ 设置失败", alert=True)

    async def _handle_toggle_chat_type(
        self, event: events.CallbackQuery, chat_type: str, query: str
    ):
        """处理切换聊天类型筛选"""
        try:
            user_id = event.sender_id

            # 初始化用户筛选器
            if user_id not in self.user_filters:
                self.user_filters[user_id] = SearchFilter()

            filters = self.user_filters[user_id]

            # 切换聊天类型
            if chat_type in filters.chat_types:
                filters.chat_types.remove(chat_type)
            else:
                filters.chat_types.append(chat_type)

            # 重新生成筛选器界面
            await self._handle_filter_menu(event, query)

        except Exception as e:
            logger.error(f"切换聊天类型失败: {e}")
            await event.answer("❌ 切换失败", alert=True)

    async def _handle_apply_filters(self, event: events.CallbackQuery, query: str):
        """处理应用筛选器"""
        try:
            user_id = event.sender_id
            filters = self.user_filters.get(user_id, SearchFilter())

            # 执行搜索（正确获取异步客户端）
            user_client = await get_user_client()
            search_system = get_search_system(user_client)
            response = await search_system.search(query, filters, 1)

            # 生成搜索结果界面
            message_text = SearchUIManager.generate_search_message(response)
            buttons = SearchUIManager.generate_pagination_buttons(response, "search")

            await event.edit(message_text, buttons=buttons, parse_mode="HTML")
            await event.answer("✅ 筛选器已应用")

        except Exception as e:
            logger.error(f"应用筛选器失败: {e}")
            await event.answer("❌ 应用失败", alert=True)

    async def _handle_back_to_search(self, event: events.CallbackQuery, query: str):
        """处理返回搜索结果"""
        try:
            user_id = event.sender_id
            filters = self.user_filters.get(user_id, SearchFilter())

            # 执行搜索（正确获取异步客户端）
            user_client = await get_user_client()
            search_system = get_search_system(user_client)
            response = await search_system.search(query, filters, 1)

            # 生成搜索结果界面
            message_text = SearchUIManager.generate_search_message(response)
            buttons = SearchUIManager.generate_pagination_buttons(response, "search")

            await event.edit(message_text, buttons=buttons, parse_mode="HTML")
            await event.answer()

        except Exception as e:
            logger.error(f"返回搜索结果失败: {e}")
            await event.answer("❌ 返回失败", alert=True)

    async def _handle_refresh_search(self, event: events.CallbackQuery, query: str):
        """处理刷新搜索"""
        try:
            user_id = event.sender_id
            filters = self.user_filters.get(user_id, SearchFilter())

            # 清理缓存并重新搜索（正确获取异步客户端）
            user_client = await get_user_client()
            search_system = get_search_system(user_client)
            search_system.cache._cache.clear()  # 清理缓存强制刷新

            response = await search_system.search(query, filters, 1)

            # 生成搜索结果界面
            message_text = SearchUIManager.generate_search_message(response)
            buttons = SearchUIManager.generate_pagination_buttons(response, "search")

            await event.edit(message_text, buttons=buttons, parse_mode="HTML")
            await event.answer("🔄 搜索已刷新")

        except Exception as e:
            logger.error(f"刷新搜索失败: {e}")
            await event.answer("❌ 刷新失败", alert=True)

    async def _handle_new_search(self, event: events.CallbackQuery):
        """处理新搜索请求"""
        try:
            message_text = (
                "🔍 <b>增强搜索系统</b>\n\n"
                "请发送搜索关键词，支持以下功能：\n"
                "• 🔍 搜索已绑定和公开群组\n"
                "• 📊 分页浏览结果\n"
                "• 🎛️ 按类型筛选\n"
                "• 🔄 多种排序方式\n"
                "• 📦 智能缓存\n\n"
                "💡 直接发送关键词开始搜索"
            )

            await event.edit(message_text, buttons=[], parse_mode="HTML")
            await event.answer("请发送搜索关键词")

        except Exception as e:
            logger.error(f"处理新搜索失败: {e}")
            await event.answer("❌ 操作失败", alert=True)

    async def _handle_bind_chat(self, event: events.CallbackQuery, chat_id_str: str):
        """处理绑定聊天"""
        try:
            # 这里可以调用绑定功能
            # 暂时先显示提示
            await event.answer(f"🔗 绑定功能开发中，聊天ID: {chat_id_str}", alert=True)

        except Exception as e:
            logger.error(f"绑定聊天失败: {e}")
            await event.answer("❌ 绑定失败", alert=True)

    async def _handle_show_detail(self, event: events.CallbackQuery, result_id: str):
        """处理显示详情"""
        try:
            # 这里可以显示详细信息
            # 暂时先显示提示
            await event.answer(f"📋 详情功能开发中，ID: {result_id}", alert=True)

        except Exception as e:
            logger.error(f"显示详情失败: {e}")
            await event.answer("❌ 显示失败", alert=True)


# 全局搜索回调处理器实例
_search_callback_handler = None


def get_search_callback_handler() -> SearchCallbackHandler:
    """获取全局搜索回调处理器实例"""
    global _search_callback_handler
    if _search_callback_handler is None:
        _search_callback_handler = SearchCallbackHandler()
    return _search_callback_handler


async def handle_search_callback(event):
    """处理搜索回调的包装函数，供外部调用"""
    handler = get_search_callback_handler()
    return await handler.handle_search_callback(event)
