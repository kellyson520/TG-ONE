"""
新菜单系统的回调处理器
"""

import traceback

import logging
import os
from telethon import Button

from handlers.button.new_menu_system import new_menu_system

logger = logging.getLogger(__name__)


async def handle_toggle_setting(event, setting_key):
    """处理全局设置的切换"""
    try:
        from services.forward_settings_service import forward_settings_service

        result = await forward_settings_service.toggle_global_boolean(setting_key)
        if not result.get("success"):
            await event.answer("操作失败", alert=True)
            return
        new_value = result.get("new_value")

        setting_names = {
            "allow_text": "放行文本",
            "allow_emoji": "放行表情包",
            "media_extension_enabled": "媒体扩展过滤",
        }

        setting_name = setting_names.get(setting_key, setting_key)
        status = "开启" if new_value else "关闭"
        await event.answer(f"{setting_name}已{status}")

        # 刷新筛选设置页面
        await new_menu_system.show_filter_settings(event)

    except Exception as e:
        logger.error(f"切换设置失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_toggle_extension_mode(event):
    """处理扩展模式切换"""
    try:
        from services.forward_settings_service import forward_settings_service

        r = await forward_settings_service.toggle_extension_mode()
        if not r.get("success"):
            await event.answer("操作失败", alert=True)
            return
        new_mode = r.get("new_mode") or "blacklist"

        mode_name = "白名单" if new_mode == "whitelist" else "黑名单"
        await event.answer(f"扩展过滤模式已切换为{mode_name}")

        # 刷新筛选设置页面
        await new_menu_system.show_filter_settings(event)

    except Exception as e:
        logger.error(f"切换扩展模式失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_toggle_media_type(event, media_type):
    """处理媒体类型切换"""
    try:
        from services.forward_settings_service import forward_settings_service

        result = await forward_settings_service.toggle_media_type(media_type)

        if result:
            settings = await forward_settings_service.get_global_media_settings()
            is_enabled = settings["media_types"].get(media_type, False)

            type_names = {
                "image": "图片",
                "video": "视频",
                "audio": "音乐",
                "voice": "语音",
                "document": "文档",
            }

            type_name = type_names.get(media_type, media_type)
            status = "允许" if is_enabled else "禁止"
            await event.answer(f"{type_name}已{status}")

            # 刷新媒体类型页面（避免未修改错误，加延时）
            try:
                await new_menu_system.show_media_types(event)
            except Exception as e:
                if "not modified" in str(e).lower():
                    await event.answer("已更新")
                else:
                    raise
        else:
            await event.answer("操作失败", alert=True)

    except Exception as e:
        logger.error(f"切换媒体类型失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_toggle_media_duration(event):
    """处理媒体时长过滤切换"""
    try:
        from services.forward_settings_service import forward_settings_service

        settings = await forward_settings_service.get_global_media_settings()
        current_value = settings.get("media_duration_enabled", False)
        new_value = not current_value
        await forward_settings_service.update_global_media_setting(
            "media_duration_enabled", new_value
        )

        status = "开启" if new_value else "关闭"
        await event.answer(f"媒体时长过滤已{status}")

        # 刷新媒体时长设置页面
        await new_menu_system.show_media_duration_settings(event)

    except Exception as e:
        logger.error(f"切换媒体时长过滤失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_set_duration_range(event):
    """处理设置时长范围 - 进入起止选择页"""
    try:
        # 进入先选起始或结束的分流菜单
        buttons = [
            [Button.inline("设置起始时长", "new_menu:set_duration_start")],
            [Button.inline("设置结束时长(0视为∞)", "new_menu:set_duration_end")],
            [Button.inline("👈 返回上一级", "new_menu:media_duration_settings")],
        ]
        # 添加时间戳避免内容重复
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")
        text = f"请选择要设置的时长边界：\n\n更新时间: {timestamp}"
        await event.edit(text, buttons=buttons)
    except Exception as e:
        logger.error(f"设置时长范围失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_set_duration_start(event):
    """处理设置时长起始点"""
    try:
        await new_menu_system.show_duration_range_picker(event, "min")
    except Exception as e:
        logger.error(f"设置时长起始点失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_set_duration_end(event):
    """处理设置时长终止点"""
    try:
        await new_menu_system.show_duration_range_picker(event, "max")
    except Exception as e:
        logger.error(f"设置时长终止点失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_save_duration_settings(event):
    """处理保存时长设置"""
    try:
        await event.answer("✅ 时长设置已自动保存")

    except Exception as e:
        logger.error(f"保存时长设置失败: {str(e)}")
        await event.answer("保存失败", alert=True)


async def handle_toggle_media_size_filter(event):
    """处理媒体大小过滤切换"""
    try:
        from services.forward_settings_service import forward_settings_service

        settings = await forward_settings_service.get_global_media_settings()
        current_value = settings.get("media_size_filter_enabled", False)
        new_value = not current_value
        ok = await forward_settings_service.update_global_media_setting(
            "media_size_filter_enabled", new_value
        )
        if not ok:
            await event.answer("操作失败", alert=True)
            return

        status = "开启" if new_value else "关闭"
        await event.answer(f"媒体大小过滤已{status}")

        # 刷新媒体大小设置页面
        await new_menu_system.show_media_size_settings(event)

    except Exception as e:
        logger.error(f"切换媒体大小过滤失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_toggle_media_size_alert(event):
    """处理媒体大小超限提示切换"""
    try:
        from services.forward_settings_service import forward_settings_service

        settings = await forward_settings_service.get_global_media_settings()
        current_value = settings.get("media_size_alert_enabled", False)
        new_value = not current_value
        ok = await forward_settings_service.update_global_media_setting(
            "media_size_alert_enabled", new_value
        )
        if not ok:
            await event.answer("操作失败", alert=True)
            return

        status = "开启" if new_value else "关闭"
        await event.answer(f"媒体大小超限提示已{status}")

        # 刷新媒体大小设置页面
        await new_menu_system.show_media_size_settings(event)

    except Exception as e:
        logger.error(f"切换媒体大小超限提示失败: {str(e)}")
        await event.answer("操作失败", alert=True)


async def handle_new_menu_callback(event):
    """处理新菜单回调"""
    data = event.data.decode("utf-8")
    parts = data.split(":")
    action = parts[1]

    if action == "main" or action == "main_menu":
        from controllers.menu_controller import menu_controller
        await menu_controller.show_main_menu(event)
    elif action == "forward_management":
        await new_menu_system.show_forward_management(event)
    elif action == "list_rules":
        page = int(parts[2]) if len(parts) > 2 else 1
        await new_menu_system.show_rule_list(event, page)
    else:
        # 调用现有的回调处理器处理其他情况
        from models.models import AsyncSessionManager

        async with AsyncSessionManager() as session:
            message = await event.get_message()
            action_data = data[9:]  # 去掉 'new_menu:' 前缀
            await callback_new_menu_handler(event, action_data, session, message, data)


async def callback_new_menu_handler(event, action_data, session, message, data):
    """新菜单系统的统一回调处理器"""
    try:
        try:
            logger.info(f"[menu] new_menu action_data={action_data}")
        except Exception:
            pass
        # action_data 已经是解析后的动作（比如 "toggle_media_duration" 或 "main_menu"）
        # 对于复合动作（如 "rule_detail_settings:123"），可能还需要进一步解析
        if ":" in action_data:
            parts = action_data.split(":")
            action = parts[0]
            extra_data = parts[1:]
        else:
            action = action_data
            extra_data = []
        try:
            logger.info(f"[menu] parsed action={action} extra={extra_data}")
        except Exception:
            pass

        # 根据action分发到对应的处理函数
        from controllers.menu_controller import menu_controller
        
        # 1. 核心中心入口
        if action in ["main_menu", "main"]:
            await menu_controller.show_main_menu(event)
        elif action == "forward_hub":
            await menu_controller.show_forward_hub(event)
        elif action == "dedup_hub":
            await menu_controller.show_dedup_hub(event)
        elif action == "analytics_hub":
            await menu_controller.show_analytics_hub(event)
        elif action == "system_hub":
            await menu_controller.show_system_hub(event)
        elif action == "main_menu_refresh":
            await menu_controller.show_main_menu(event, force_refresh=True)
            await event.answer("✅ 数据看板已刷新")
        elif action == "help_guide":
            await menu_controller.show_help_guide(event)
            
        # 2. 规则管理
        elif action == "list_rules":
            page = int(extra_data[0]) if extra_data else 0
            await menu_controller.show_rule_list(event, page=page)
        elif action == "rule_detail":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.show_rule_detail(event, rule_id)
        elif action == "toggle_rule":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.toggle_rule_status(event, rule_id)
        elif action == "delete_rule_confirm":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.delete_rule_confirm(event, rule_id)
        elif action == "delete_rule_do":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.delete_rule_do(event, rule_id)
        elif action == "keywords":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.show_manage_keywords(event, rule_id)
        elif action == "replaces":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.show_manage_replace_rules(event, rule_id)
        elif action == "add_keyword":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.enter_add_keyword_state(event, rule_id)
        elif action == "clear_keywords_confirm":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.clear_keywords_confirm(event, rule_id)
        elif action == "clear_keywords_do":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.clear_keywords_do(event, rule_id)
        elif action == "add_replace":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.enter_add_replace_state(event, rule_id)
        elif action == "clear_replaces_confirm":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.clear_replaces_confirm(event, rule_id)
        elif action == "clear_replaces_do":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.clear_replaces_do(event, rule_id)
        elif action == "rule_basic_settings":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.show_rule_basic_settings(event, rule_id)
        elif action == "rule_display_settings":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.show_rule_display_settings(event, rule_id)
        elif action == "rule_advanced_settings":
            rule_id = int(extra_data[0]) if extra_data else 0
            await menu_controller.show_rule_advanced_settings(event, rule_id)
        elif action == "toggle_rule_set":
            rule_id = int(extra_data[0]) if extra_data else 0
            key = extra_data[1] if len(extra_data) > 1 else ""
            await menu_controller.toggle_rule_setting_new(event, rule_id, key)
            
        # 3. 系统与会话管理
        elif action == "system_settings":
            await new_menu_system.show_system_settings(event)
        elif action == "db_backup":
            await menu_controller.show_db_backup(event)
        elif action == "backup_current":
            await new_menu_system.confirm_backup(event)
        elif action == "do_backup":
            await new_menu_system.do_backup(event)
        elif action == "view_backups":
            await new_menu_system.show_backup_history(event)
        elif action == "system_overview":
            await new_menu_system.show_system_overview(event)
        elif action == "cache_cleanup":
            await menu_controller.show_cache_cleanup(event)
        elif action == "do_cleanup":
            await new_menu_system.do_cache_cleanup(event)
        elif action == "session_management":
            await menu_controller.show_session_management(event)
        elif action == "history_messages":
            await menu_controller.show_history_messages(event)
        elif action == "forward_management":
            await menu_controller.show_rule_management(event)
        elif action == "cache_cleanup":
            # 缓存清理确认
            await new_menu_system.confirm_cache_cleanup(event)
        elif action == "do_cleanup":
            await new_menu_system.do_cache_cleanup(event)
        elif action == "session_management":
            # 进入会话管理菜单
            await new_menu_system.show_session_management(event)
        elif action == "session_dedup":
            # 会话内去重入口
            await new_menu_system.show_session_dedup_menu(event)
        elif action == "start_dedup_scan":
            # 使用统一的扫描方法
            await new_menu_system.start_dedup_scan(event)
        elif action == "dedup_results":
            # 显示智能去重扫描结果
            await new_menu_system.show_dedup_results(event)
        elif action == "delete_all_duplicates":
            # 显示删除确认
            await new_menu_system.confirm_delete_all_duplicates(event)
        elif action == "execute_delete_all":
            # 执行删除所有重复项
            await new_menu_system.execute_delete_all_duplicates(event)
        elif action == "keep_all_duplicates":
            # 实现保留所有重复项
            from handlers.button.session_management import session_manager

            success, message = await session_manager.delete_duplicate_messages(
                event, mode="keep"
            )
            if success:
                await event.answer("✅ 已保留所有重复项")
                await new_menu_system.show_session_dedup_menu(event)
            else:
                await event.answer(f"❌ 操作失败: {message}")
        elif action == "select_delete_duplicates":
            # 进入选择删除界面
            await new_menu_system.show_select_delete_menu(event)
        elif action.startswith("toggle_select"):
            try:
                # new_menu:toggle_select:{signature}
                signature = extra_data[0] if extra_data else ""
                from handlers.button.session_management import session_manager

                await session_manager.toggle_select_signature(event.chat_id, signature)
                await new_menu_system.show_select_delete_menu(event)
            except Exception as e:
                logger.error(f"切换选择失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "delete_selected_duplicates":
            from handlers.button.session_management import session_manager

            success, message = await session_manager.delete_duplicate_messages(
                event, mode="select"
            )
            if success:
                await event.answer("✅ 已删除选中重复项")
                await new_menu_system.show_session_dedup_menu(event)
            else:
                await event.answer(f"❌ 删除失败: {message}")
        elif action == "delete_session_messages":
            # 进入会话消息删除菜单
            await new_menu_system.show_delete_session_messages_menu(event)
        elif action == "time_range_selection":
            # 会话删除的时间范围设置
            await new_menu_system.show_time_range_selection(event)
        elif action == "session_dedup_time_range":
            # 会话去重的时间范围设置（与删除共享同一页面）
            from handlers.button.session_management import session_manager

            session_manager.set_time_picker_context(event.chat_id, "dedup")
            await new_menu_system.show_time_range_selection(event)
        elif action == "open_session_time":
            # 会话时间范围：打开分量选择页
            try:
                side = extra_data[0]
                unit = extra_data[1]
                await new_menu_system.show_single_unit_duration_picker(
                    event,
                    "min" if side == "min" else "max",
                    {
                        "days": "days",
                        "hours": "hours",
                        "minutes": "minutes",
                        "seconds": "seconds",
                    }[unit],
                )
            except Exception as e:
                logger.error(f"打开会话时间分量选择失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "open_session_date":
            # 会话时间范围：打开 年/月/日 数字选择器
            try:
                side = extra_data[0]  # start/end
                field = extra_data[1]  # year/month/day
                await new_menu_system.show_session_numeric_picker(
                    event, "start" if side == "start" else "end", field
                )
            except Exception as e:
                logger.error(f"打开会话日期选择器失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "select_start_time":
            from handlers.button.modules.history import history_module

            await history_module.show_start_time_menu(event)
        elif action == "select_end_time":
            from handlers.button.modules.history import history_module

            await history_module.show_end_time_menu(event)
        elif action == "select_days":
            # 兼容旧入口：默认走会话时间范围
            await new_menu_system.show_day_picker(event)
        elif action == "select_days" and extra_data and extra_data[0] == "history":
            # 历史时间范围-快速选择天数（与新模块配合，返回历史路径）
            from handlers.button.session_management import session_manager

            session_manager.set_time_picker_context(event.chat_id, "history")
            await new_menu_system.show_day_picker(event)
        elif action == "select_year":
            # 兼容旧入口：统一到新模块的数字选择器
            try:
                extra_context = (
                    data.split(":")[-1]
                    if ":" in data and len(data.split(":")) > 2
                    else None
                )
                side = "start"
                if extra_context == "history_start":
                    side = "start"
                elif extra_context == "history_end":
                    side = "end"
                from handlers.button.modules.history import history_module

                await history_module.show_numeric_picker(event, side, "year")
            except Exception as e:
                logger.error(f"打开年份选择器失败: {str(e)}")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
        elif action == "select_month":
            try:
                extra_context = (
                    data.split(":")[-1]
                    if ":" in data and len(data.split(":")) > 2
                    else None
                )
                side = "start"
                if extra_context == "history_start":
                    side = "start"
                elif extra_context == "history_end":
                    side = "end"
                from handlers.button.modules.history import history_module

                await history_module.show_numeric_picker(event, side, "month")
            except Exception as e:
                logger.error(f"打开月份选择器失败: {str(e)}")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
        elif action == "select_day_of_month":
            try:
                extra_context = (
                    data.split(":")[-1]
                    if ":" in data and len(data.split(":")) > 2
                    else None
                )
                side = "start"
                if extra_context == "history_start":
                    side = "start"
                elif extra_context == "history_end":
                    side = "end"
                from handlers.button.modules.history import history_module

                await history_module.show_numeric_picker(event, side, "day")
            except Exception as e:
                logger.error(f"打开日期选择器失败: {str(e)}")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
        elif action == "set_time":
            # new_menu:set_time:{start|end}:{hour|minute}:{val}
            try:
                time_type = extra_data[0]
                unit = extra_data[1]
                value = int(extra_data[2])
                from handlers.button.session_management import session_manager

                await session_manager.set_time_component(
                    event.chat_id, time_type, unit, value
                )
                # 返回到对应的起始/结束时间菜单
                from handlers.button.modules.history import history_module

                if time_type == "start":
                    await history_module.show_start_time_menu(event)
                else:
                    await history_module.show_end_time_menu(event)
            except Exception as e:
                logger.error(f"设置时间失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_days":
            try:
                days = int(extra_data[0]) if extra_data else 0
                from handlers.button.session_management import session_manager

                await session_manager.set_days(event.chat_id, days)
                # 返回会话时间范围页
                await new_menu_system.show_time_range_selection(event)
            except Exception as e:
                logger.error(f"设置天数失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_year":
            try:
                year = int(extra_data[0]) if extra_data else 0
                from handlers.button.session_management import session_manager

                await session_manager.set_year(event.chat_id, year)
                await event.answer("✅ 已设置年份")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
            except Exception as e:
                logger.error(f"设置年份失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_month":
            try:
                month = int(extra_data[0]) if extra_data else 0
                from handlers.button.session_management import session_manager

                await session_manager.set_month(event.chat_id, month)
                await event.answer("✅ 已设置月份")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
            except Exception as e:
                logger.error(f"设置月份失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_dom":
            try:
                dom = int(extra_data[0]) if extra_data else 0
                from handlers.button.session_management import session_manager

                await session_manager.set_day_of_month(event.chat_id, dom)
                await event.answer("✅ 已设置日期")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
            except Exception as e:
                logger.error(f"设置日期失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_history_year":
            try:
                year = int(extra_data[0]) if extra_data else 0
                from handlers.button.session_management import session_manager

                await session_manager.set_year(event.chat_id, year)
                await event.answer(f"✅ 已设置年份: {year if year > 0 else '不限'}")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
            except Exception as e:
                logger.error(f"设置历史年份失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_history_month":
            try:
                month = int(extra_data[0]) if extra_data else 0
                from handlers.button.session_management import session_manager

                await session_manager.set_month(event.chat_id, month)
                await event.answer(f"✅ 已设置月份: {month if month > 0 else '不限'}月")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
            except Exception as e:
                logger.error(f"设置历史月份失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_time_field":
            try:
                if len(extra_data) >= 3:
                    side = extra_data[0]  # start/end
                    field = extra_data[1]  # year/month/day/seconds
                    value = int(extra_data[2])

                    from handlers.button.session_management import session_manager

                    await session_manager.set_time_field(
                        event.chat_id, side, field, value
                    )

                    field_name = {
                        "year": "年份",
                        "month": "月份",
                        "day": "日期",
                        "seconds": "时间",
                    }[field]
                    side_name = "起始" if side == "start" else "结束"

                    if field == "seconds":
                        # 显示时分秒
                        h = value // 3600
                        m = (value % 3600) // 60
                        s = value % 60
                        await event.answer(
                            f"✅ 已设置{side_name}{field_name}: {h:02d}:{m:02d}:{s:02d}"
                        )
                    else:
                        display_value = (
                            f"{value}{field_name[0]}" if value > 0 else "不限"
                        )
                        await event.answer(
                            f"✅ 已设置{side_name}{field_name}: {display_value}"
                        )

                    # 返回对应的数字选择器
                    from handlers.button.modules.history import history_module

                    await history_module.show_numeric_picker(event, side, field)
                else:
                    await event.answer("参数不足", alert=True)
            except Exception as e:
                logger.error(f"设置时间字段失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_all_time_zero":
            try:
                from handlers.button.session_management import session_manager

                # 将所有时间参数设为0（表示获取全部消息）
                await session_manager.set_time_field(event.chat_id, "start", "year", 0)
                await session_manager.set_time_field(event.chat_id, "start", "month", 0)
                await session_manager.set_time_field(event.chat_id, "start", "day", 0)
                await session_manager.set_time_field(
                    event.chat_id, "start", "seconds", 0
                )
                await session_manager.set_time_field(event.chat_id, "end", "year", 0)
                await session_manager.set_time_field(event.chat_id, "end", "month", 0)
                await session_manager.set_time_field(event.chat_id, "end", "day", 0)
                await session_manager.set_time_field(event.chat_id, "end", "seconds", 0)
                await event.answer("✅ 已重置为全部时间")
                # 保持在时间范围选择器页面，而不是跳转到设置页面
                from handlers.button.modules.history import history_module

                await history_module.show_time_range_selection(event)
            except Exception as e:
                logger.error(f"重置全部时间失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "save_days":
            await new_menu_system.show_time_range_selection(event)
        elif action == "save_time_range":
            # 实现保存时间范围
            from handlers.button.session_management import session_manager

            success = await session_manager.save_time_range_settings(event.chat_id)
            if success:
                await event.answer("✅ 时间范围设置已保存")
                await new_menu_system.show_time_range_selection(event)
            else:
                await event.answer("❌ 保存失败")
        elif action == "start_delete_messages":
            # 实现开始删除消息
            from handlers.button.session_management import session_manager

            success, message = await session_manager.delete_session_messages_by_filter(
                event
            )
            if success:
                await event.answer("✅ 开始删除消息")
                await new_menu_system.show_delete_session_messages_menu(event)
            else:
                await event.answer(f"❌ 启动失败: {message}")
        elif action == "preview_delete":
            # 预览将要删除的消息
            try:
                await new_menu_system.show_preview_delete(event)
            except Exception as e:
                logger.error(f"显示删除预览失败: {e}")
                await event.answer("预览失败", alert=True)
        elif action == "preview_delete_refresh":
            # 刷新预览
            try:
                await new_menu_system.show_preview_delete(event)
            except Exception as e:
                logger.error(f"刷新删除预览失败: {e}")
                await event.answer("刷新失败", alert=True)
        elif action == "confirm_delete":
            # 二次确认后执行删除
            from handlers.button.session_management import session_manager

            success, message = await session_manager.delete_session_messages_by_filter(
                event
            )
            try:
                if success:
                    await event.answer("✅ 删除任务已启动")
                else:
                    await event.answer(f"❌ 删除失败: {message}")
            except Exception:
                pass
            await new_menu_system.show_delete_session_messages_menu(event)
        elif action == "pause_delete":
            # 实现暂停删除
            from handlers.button.session_management import session_manager

            success = await session_manager.pause_delete_task(event.chat_id)
            if success:
                await event.answer("⏸️ 删除任务已暂停")
            else:
                await event.answer("❌ 暂停失败")
        elif action == "stop_delete":
            # 实现停止删除
            from handlers.button.session_management import session_manager

            success = await session_manager.stop_delete_task(event.chat_id)
            if success:
                await event.answer("⏹️ 删除任务已停止")
            else:
                await event.answer("❌ 停止失败")
        elif action == "message_filter":
            # 实现消息筛选
            await new_menu_system.show_message_filter_menu(event)
        elif action == "filter_media_types":
            # 会话删除-筛选：媒体类型
            await new_menu_system.show_media_types(event)
        elif action == "filter_allow_text":
            # 会话删除-筛选：放行文本开关（复用全局切换）
            await handle_toggle_setting(event, "allow_text")
        elif action == "filter_media_extension":
            # 会话删除-筛选：扩展名设置
            await new_menu_system.show_media_extension_settings(event)
        elif action == "filter_media_size":
            # 会话删除-筛选：媒体大小
            await new_menu_system.show_media_size_settings(event)
        elif action == "filter_media_duration":
            # 会话删除-筛选：媒体时长
            await new_menu_system.show_media_duration_settings(event)
        elif action == "save_message_filter":
            # 占位：此处可落库保存筛选配置，当前仅提示成功并返回
            try:
                await event.answer("✅ 已保存筛选配置")
            except Exception:
                pass
            await new_menu_system.show_delete_session_messages_menu(event)
        elif action == "forward_management":
            await new_menu_system.show_forward_management(event)
        elif action == "forward_search":
            await new_menu_system.show_forward_search(event)
        elif action == "forward_stats_detailed":
            try:
                from controllers.menu_controller import menu_controller

                # 复用分析中心的详细统计渲染
                await menu_controller.show_analytics_hub(event)
            except Exception as e:
                logger.error(f"显示转发统计失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "global_forward_settings":
            try:
                # 跳转到全局筛选设置
                await new_menu_system.show_filter_settings(event)
            except Exception as e:
                logger.error(f"显示全局设置失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "forward_performance":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_realtime_monitor(event)
            except Exception as e:
                logger.error(f"显示性能监控失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "channel_management_global":
            await new_menu_system.show_channel_management_global(event)
        elif action == "current_chat_rules" or action.startswith("current_chat_rules:"):
            # 在群组环境下直接委托给老菜单的规则选择（只显示本群相关规则）
            try:
                from .callback_handlers import handle_callback as legacy_handle

                # 构造老菜单数据：'settings' 会触发规则选择，仅显示与当前群关联的规则
                event.data = b"settings"
                await legacy_handle(event)
                return
            except Exception as e:
                logger.error(f"委托老菜单显示当前群规则失败: {str(e)}")
                # 回退到新菜单原实现
                if ":" in action:
                    chat_id = action.split(":")[1]
                else:
                    chat_id = str(event.chat_id)
                await new_menu_system.show_current_chat_rules(event, chat_id)
        elif action.startswith("global_rules_page:"):
            page = int(action.split(":")[1])
            await new_menu_system.show_channel_management_global_page(event, page)
        elif action.startswith("current_chat_rules_page:"):
            parts_action = action.split(":")
            chat_id = parts_action[1]
            page = int(parts_action[2])
            await new_menu_system.show_current_chat_rules_page(event, chat_id, page)
        elif action.startswith("rule_detail_settings:"):
            # 处理带规则ID的规则详细设置
            rule_id = int(action.split(":")[1])
            await new_menu_system.show_rule_detail_settings(event, rule_id)
        elif action == "rule_detail_settings":
            # 显示规则选择菜单，然后进入老菜单的规则设置（保持向后兼容）
            await new_menu_system.show_rule_selection_for_settings(event)
        elif action == "channel_management":
            # 兼容旧回调，映射到全局频道管理
            await new_menu_system.show_channel_management_global(event)
        elif action == "rule_management":
            await new_menu_system.show_rule_management(event)
        elif action == "multi_source_management":
            await new_menu_system.show_multi_source_management(event)
        elif action == "rule_page":
            page = int(extra_data[0]) if extra_data else 0
            await new_menu_system.show_rule_management(event, page)
        elif action == "multi_source_page":
            page = int(extra_data[0]) if extra_data else 0
            await new_menu_system.show_multi_source_management(event, page)
        elif action == "toggle_rule_status_multi" and extra_data:
            try:
                rule_id = int(extra_data[0])
                enabled = (
                    extra_data[1].lower() == "true" if len(extra_data) > 1 else True
                )
                # 直接调用服务层切换状态，避免跳转到规则详情页
                from services.rule_management_service import rule_management_service

                result = await rule_management_service.toggle_rule_status(
                    rule_id, enabled
                )
                if result.get("success"):
                    await event.answer(f"规则已{'启用' if enabled else '禁用'}")
                else:
                    await event.answer(
                        f"操作失败: {result.get('error','未知错误')}", alert=True
                    )
                # 刷新多源管理页
                await new_menu_system.show_multi_source_management(event)
            except Exception as e:
                logger.error(f"切换规则状态(多源)失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "toggle_rule":
            # 保留此回调以防某些地方仍在使用
            rule_id = int(extra_data[0]) if extra_data else 0
            from handlers.button.forward_management import forward_manager

            success, new_state = await forward_manager.toggle_rule_status(rule_id)
            if success:
                await event.answer(f"规则已{'启用' if new_state else '禁用'}")
                # 根据上下文返回不同页面
                await new_menu_system.show_rule_management(event)
            else:
                await event.answer("切换规则状态失败")
        elif action == "manage_multi_source":
            rule_id = int(extra_data[0]) if extra_data else 0
            # 实现多源管理详细页面
            await new_menu_system.show_multi_source_detail(event, rule_id)
        elif action == "filter_settings":
            await new_menu_system.show_filter_settings(event)
        elif action == "media_types":
            await new_menu_system.show_media_types(event)
        elif action == "allow_text":
            # 与 toggle_allow_text 统一：保持后向兼容
            await handle_toggle_setting(event, "allow_text")
        elif action == "toggle_allow_emoji":
            await handle_toggle_setting(event, "allow_emoji")
        elif action == "media_types":
            await new_menu_system.show_media_types(event)
        elif action == "history_messages":
            await new_menu_system.show_history_messages(event)
        elif action == "history_task_actions":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_task_actions(event)
            except Exception as e:
                logger.error(f"显示历史任务操作子菜单失败: {str(e)}")
                await event.answer("加载失败", alert=True)
        elif action == "history_task_list":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_task_list(event)
            except Exception as e:
                logger.error(f"加载历史任务列表失败: {str(e)}")
                await event.answer("加载失败", alert=True)
        elif action == "history_dry_run":
            try:
                # 干跑：仅统计不发送
                from handlers.button.session_management import session_manager

                user_id = event.chat_id
                rule_id = await session_manager.get_selected_rule(user_id)
                if not rule_id:
                    await event.answer("请先选择规则", alert=True)
                    return
                logger.info(
                    f"[干跑] 回调进入 history_dry_run, chat={user_id}, rule={rule_id}"
                )
                # 先即时反馈，避免长时间无响应
                try:
                    await event.answer("⏳ 正在统计，请稍候…")
                except Exception:
                    pass
                # 再次校验 rule 从数据库读取标题便于确认
                try:
                    from models.models import ForwardRule as _FR
                    from models.models import get_session as _gs

                    with _gs() as _s:
                        _r = _s.query(_FR).get(int(rule_id)) if rule_id else None
                        logger.info(
                            f"[干跑] 选中规则校验: id={rule_id}, "
                            f"source={getattr(getattr(_r,'source_chat',None),'name',None)}, "
                            f"target={getattr(getattr(_r,'target_chat',None),'name',None)}"
                        )
                except Exception:
                    pass
                # 干跑：采样不使用本地轻量去重集合，避免二次点击显示 0 条
                # 限制最大收集，避免长时间阻塞
                total, samples = await session_manager.preview_history_messages(
                    event, sample=10, collect_full=True, max_collect=800
                )
                logger.info(
                    f"[干跑] history_dry_run 完成, total={total}, samples={len(samples)}"
                )
                try:
                    # 对比仅按时间范围统计，快速判断偏差来自筛选还是时间窗口/读取
                    tr_total, tr_in = await session_manager.count_history_in_range(
                        event
                    )
                    logger.info(
                        f"[干跑] 仅时间范围统计: in_range={tr_in}, 预览通过={total}"
                    )
                except Exception:
                    pass
                if total == 0 and not samples:
                    # 运行诊断工具，提供详细的问题分析
                    try:
                        diagnosis = (
                            await session_manager.diagnose_history_filter_issues(event)
                        )
                        hint = "🔍 **问题诊断：**\n" + "\n".join(diagnosis)
                    except Exception:
                        # 如果诊断失败，使用原来的简单提示
                        hint = (
                            "可能原因：\n"
                            "- 时间范围过窄或未设置（建议改为全部时间或最近7天）\n"
                            "- 筛选条件过严（媒体类型/关键词/仅文本/仅媒体）\n"
                            "- 源会话确实没有符合条件的消息\n"
                        )
                else:
                    hint = ""
                # 附加最近一次干跑的统计分布（即使 total=0 也展示）
                try:
                    dbg = session_manager.get_last_dry_run_debug(event.chat_id)
                    if dbg:
                        stats = (
                            "\n\n📈 过滤统计：\n"
                            f"- 扫描: {dbg.get('total_scanned', 0)}\n"
                            f"- 时间范围外: {dbg.get('before_time_range', 0)}\n"
                            f"- 时分秒过滤: {dbg.get('time_filtered', 0)}\n"
                            f"- 内容筛选过滤: {dbg.get('content_filtered', 0)}\n"
                            f"- 通过: {dbg.get('passed', 0)}\n"
                        )
                    else:
                        stats = ""
                except Exception:
                    stats = ""

                text = (
                    "🧪 **干跑（不发送）**\n\n"
                    f"预计处理: {total} 条\n\n"
                    + (
                        "\n".join(samples)
                        if samples
                        else "无样本（请检查时间范围/筛选条件）"
                    )
                    + ("\n\n" + hint if hint else "")
                    + stats
                )
                from telethon.tl.custom import Button

                buttons = []
                if total > 0:
                    buttons.append(
                        [Button.inline("📖 查看完整分页", "new_menu:dry_run_page:0")]
                    )
                else:
                    # 为0条消息时提供快速修复选项
                    buttons.extend(
                        [
                            [
                                Button.inline(
                                    "⏰ 调整时间范围", "new_menu:history_time_range"
                                )
                            ],
                            [
                                Button.inline(
                                    "🎯 调整筛选条件", "new_menu:filter_settings"
                                )
                            ],
                            [
                                Button.inline(
                                    "🧪 跳过筛选测试",
                                    "new_menu:history_dry_run_no_filter",
                                )
                            ],
                            [
                                Button.inline(
                                    "📊 快速统计(服务端)",
                                    "new_menu:history_quick_stats",
                                )
                            ],
                            [Button.inline("🔄 重新诊断", "new_menu:history_dry_run")],
                        ]
                    )
                buttons.append(
                    [Button.inline("👈 返回操作", "new_menu:history_task_actions")]
                )
                await event.respond(text, buttons=buttons)
            except Exception as e:
                logger.error(f"干跑失败: {e}")
                await event.answer("干跑失败", alert=True)
        elif action == "history_count_videos":
            try:
                from handlers.button.session_management import session_manager

                user_id = event.chat_id
                rule_id = await session_manager.get_selected_rule(user_id)
                if not rule_id:
                    await event.answer("请先选择规则", alert=True)
                    return
                try:
                    await event.answer("⏳ 正在统计视频数量…")
                except Exception:
                    pass
                scanned, in_range = await session_manager.count_media_in_range(
                    event, media="video"
                )
                text = (
                    "🎞️ **视频数量统计**\n\n"
                    f"扫描条数: {scanned}\n"
                    f"时间范围内视频: {in_range}\n\n"
                    "提示：该统计使用服务端过滤，速度更快；若数量为0，建议扩大时间范围或检查访问权限。"
                )
                from telethon.tl.custom import Button

                buttons = [
                    [Button.inline("🧪 正常干跑", "new_menu:history_dry_run")],
                    [Button.inline("⏰ 调整时间范围", "new_menu:history_time_range")],
                    [Button.inline("👈 返回操作", "new_menu:history_task_actions")],
                ]
                await event.respond(text, buttons=buttons)
            except Exception as e:
                logger.error(f"视频数量统计失败: {e}")
                await event.answer("统计失败", alert=True)
        elif action == "history_quick_stats":
            try:
                from handlers.button.session_management import session_manager

                user_id = event.chat_id
                rule_id = await session_manager.get_selected_rule(user_id)
                if not rule_id:
                    await event.answer("请先选择规则", alert=True)
                    return
                try:
                    await event.answer("⏳ 正在快速统计(服务端)…")
                except Exception:
                    pass
                stats = await session_manager.quick_count_by_filters(event)

                # 组装展示
                def fmt(key, name):
                    v = stats.get(key, 0)
                    return f"- {name}: {v}"

                lines = [
                    fmt("all", "全部"),
                    fmt("photo", "图片"),
                    fmt("video", "视频"),
                    fmt("round_video", "圆形视频"),
                    fmt("document", "文件"),
                    fmt("voice", "语音"),
                    fmt("music", "音乐"),
                    fmt("gif", "GIF"),
                    fmt("url", "含链接"),
                    fmt("photo_video", "图/视"),
                ]
                text = (
                    "📊 **快速统计（服务端）**\n\n"
                    + "\n".join(lines)
                    + "\n\n说明：通过 Telegram 服务端过滤+计数，几乎不拉取正文，速度快、不阻塞。时间范围使用当前设置（不含时分秒）。"
                )
                from telethon.tl.custom import Button

                buttons = [
                    [Button.inline("🧪 正常干跑", "new_menu:history_dry_run")],
                    [Button.inline("⏰ 调整时间范围", "new_menu:history_time_range")],
                    [Button.inline("👈 返回操作", "new_menu:history_task_actions")],
                ]
                await event.respond(text, buttons=buttons)
            except Exception as e:
                logger.error(f"快速统计失败: {e}")
                await event.answer("统计失败", alert=True)
        elif action == "history_dry_run_no_filter":
            try:
                # 跳过筛选的干跑测试
                from handlers.button.session_management import session_manager

                user_id = event.chat_id
                rule_id = await session_manager.get_selected_rule(user_id)
                if not rule_id:
                    await event.answer("请先选择规则", alert=True)
                    return
                # 跳过所有筛选条件的干跑
                logger.info(
                    f"[干跑] 回调进入 history_dry_run_no_filter, chat={user_id}, rule={rule_id}"
                )
                total, samples = await session_manager.preview_history_messages(
                    event,
                    sample=10,
                    collect_full=False,
                    max_collect=500,
                    skip_filters=True,
                )
                logger.info(
                    f"[干跑] history_dry_run_no_filter 完成, total={total}, samples={len(samples)}"
                )
                text = "🧪 **跳过筛选测试（不发送）**\n\n" f"跳过所有筛选条件后预计处理: {total} 条\n\n" + (
                    "\n".join(samples) if samples else "仍然无样本"
                ) + (
                    f"\n\n✅ **发现 {total} 条消息！问题确实出在筛选条件上。**"
                    if total > 0
                    else "\n\n❌ **仍然是0条，问题可能是时间范围或源会话访问权限。**"
                )
                from telethon.tl.custom import Button

                buttons = [
                    [Button.inline("🎯 调整筛选条件", "new_menu:filter_settings")],
                    [Button.inline("⏰ 调整时间范围", "new_menu:history_time_range")],
                    [Button.inline("🔄 正常干跑", "new_menu:history_dry_run")],
                    [Button.inline("👈 返回操作", "new_menu:history_task_actions")],
                ]
                await event.respond(text, buttons=buttons)
            except Exception as e:
                logger.error(f"跳过筛选干跑失败: {e}")
                await event.answer("测试失败", alert=True)
        elif action.startswith("dry_run_page"):
            try:
                page = int(extra_data[0]) if extra_data else 0
                from handlers.button.session_management import session_manager

                items, pg = session_manager.get_dry_run_page(event.chat_id, page)
                header = f"🧪 干跑分页  第 {pg['page']+1}/{pg['total_pages']} 页  共 {pg['total_items']} 条（估计 {pg['estimated_total']}）\n\n"
                body = "\n\n".join(items) if items else "无数据"
                from telethon.tl.custom import Button

                nav = []
                if pg["page"] > 0:
                    nav.append(
                        Button.inline(
                            "⬅️ 上一页", f"new_menu:dry_run_page:{pg['page']-1}"
                        )
                    )
                if pg["page"] < pg["total_pages"] - 1:
                    nav.append(
                        Button.inline(
                            "下一页 ➡️", f"new_menu:dry_run_page:{pg['page']+1}"
                        )
                    )
                buttons = []
                if nav:
                    buttons.append(nav)
                buttons.append(
                    [Button.inline("👈 返回干跑", "new_menu:history_dry_run")]
                )
                await event.respond(header + body, buttons=buttons)
            except Exception as e:
                logger.error(f"干跑分页失败: {e}")
                await event.answer("分页失败", alert=True)
        elif action.startswith("history_task_detail"):
            try:
                from controllers.menu_controller import menu_controller

                tid = int(extra_data[0]) if extra_data else None
                await menu_controller.show_history_task_detail(event, tid)
            except Exception as e:
                logger.error(f"加载历史任务详情失败: {str(e)}")
                await event.answer("加载失败", alert=True)
        elif action.startswith("download_task_json"):
            try:
                from controllers.menu_controller import menu_controller

                tid = int(extra_data[0]) if extra_data else None
                await menu_controller.download_task_json(event, tid)
            except Exception as e:
                logger.error(f"下载任务JSON失败: {str(e)}")
                await event.answer("下载失败", alert=True)
        elif action.startswith("open_source_chat"):
            try:
                chat_id = int(extra_data[0]) if extra_data else 0
                if chat_id:
                    await event.respond(
                        f"源会话 ID: `{chat_id}`", parse_mode="markdown"
                    )
                else:
                    await event.answer("无源会话", alert=True)
            except Exception as e:
                logger.error(f"打开源会话失败: {e}")
                await event.answer("打开失败", alert=True)
        elif action.startswith("open_target_chat"):
            try:
                chat_id = int(extra_data[0]) if extra_data else 0
                if chat_id:
                    await event.respond(
                        f"目标会话 ID: `{chat_id}`", parse_mode="markdown"
                    )
                else:
                    await event.answer("无目标会话", alert=True)
            except Exception as e:
                logger.error(f"打开目标会话失败: {e}")
                await event.answer("打开失败", alert=True)
        elif action == "history_failed_samples":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_failed_samples(event)
            except Exception as e:
                logger.error(f"加载失败样本失败: {str(e)}")
                await event.answer("加载失败", alert=True)
        elif action == "toggle_auto_refresh":
            try:
                from handlers.button.session_management import session_manager

                msg = await event.get_message()
                enabled = await session_manager.toggle_auto_refresh(
                    event.chat_id, msg.id
                )
                await event.answer(
                    "🔄 自动刷新已开启" if enabled else "🚫 自动刷新已关闭"
                )
                # 改为跳转到当前任务页面（新架构），避免回到旧主页
                from controllers.menu_controller import menu_controller

                await menu_controller.show_current_history_task(event)
            except Exception as e:
                logger.error(f"切换自动刷新失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        # start_history_task 处理器已在下方1738行实现，移除此重复处理器
        elif action == "select_history_task":
            await new_menu_system.show_history_task_selector(event)
        elif action.startswith("select_task"):
            try:
                rid = int(extra_data[0]) if extra_data else None
                if rid is None:
                    await event.answer("缺少规则ID", alert=True)
                else:
                    from handlers.button.session_management import session_manager

                    await session_manager.set_selected_rule(event.chat_id, rid)
                # 选择后进入“历史任务操作子菜单”（下级菜单）
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_task_actions(event)
            except Exception as e:
                logger.error(f"选择历史任务失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "history_message_filter":
            from handlers.button.modules.history import history_module

            await history_module.show_message_filter_menu(event)
        elif action == "history_message_limit":
            from handlers.button.modules.history import history_module

            await history_module.show_message_limit_menu(event)
        elif action == "set_history_limit":
            # 设置历史消息数量限制
            try:
                limit = int(extra_data[0]) if extra_data else 0

                # 使用配置管理器更新配置
                from utils.core.env_config import env_config_manager

                success = env_config_manager.set_history_message_limit(limit)

                if success:
                    limit_text = f"{limit:,}" if limit > 0 else "无限制"
                    await event.answer(f"✅ 历史消息数量限制已设置为：{limit_text}")

                    # 返回消息筛选菜单
                    from handlers.button.modules.history import history_module

                    await history_module.show_message_filter_menu(event)
                else:
                    await event.answer("❌ 设置失败，请重试", alert=True)

            except Exception as e:
                logger.error(f"设置历史消息数量限制失败: {e}")
                await event.answer("❌ 设置失败，请重试", alert=True)
        elif action == "history_time_range":
            from handlers.button.modules.history import history_module

            await history_module.show_time_range_selection(event)
        elif action == "open_history_time":
            # 参数: side:field (start/end : year/month/day/hour/minute/second)
            try:
                side = extra_data[0] if len(extra_data) > 0 else "start"
                field = extra_data[1] if len(extra_data) > 1 else "year"
                from handlers.button.modules.history import history_module

                await history_module.show_numeric_picker(event, side, field)
            except Exception as e:
                logger.error(f"打开历史数字选择器失败: {e}")
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
        elif action == "history_start_time_menu":
            from handlers.button.modules.history import history_module

            await history_module.show_start_time_menu(event)
        elif action == "history_end_time_menu":
            from handlers.button.modules.history import history_module

            await history_module.show_end_time_menu(event)
        elif action == "history_delay_settings":
            # 统一通过控制器渲染延迟设置页，避免新旧菜单混用
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_delay_settings(event)
            except Exception:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_delay_settings(event)
        elif action == "set_start_time":
            from handlers.button.modules.history import history_module

            await history_module.show_start_time_menu(event)
        elif action == "set_end_time":
            from handlers.button.modules.history import history_module

            await history_module.show_end_time_menu(event)
        elif action == "confirm_time_range":
            try:
                await event.answer("✅ 已保存时间范围")
            except Exception:
                pass
            # 智能返回：根据上下文返回到合适的页面
            try:
                # 检查消息内容，判断来源页面
                message = await event.get_message()
                message_text = message.text if message else ""

                # 如果消息中包含快速统计相关内容，返回到任务操作页面以便继续统计
                # 否则正常返回到任务操作页面
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_task_actions(event)
            except Exception:
                # 兜底：回到历史消息主菜单
                await new_menu_system.show_history_messages(event)
        elif action == "history_filter_media_types":
            from handlers.button.modules.history import history_module

            await history_module.show_media_types(event)
        elif action == "history_filter_media_duration":
            from handlers.button.modules.history import history_module

            await history_module.show_media_duration_settings(event)
        elif action == "history_toggle_allow_text":
            await handle_toggle_setting(event, "allow_text")
        elif action == "history_toggle_image":
            await handle_toggle_media_type(event, "image")
        elif action == "history_toggle_video":
            await handle_toggle_media_type(event, "video")
        elif action == "history_toggle_music":
            await handle_toggle_media_type(event, "audio")
        elif action == "history_toggle_voice":
            await handle_toggle_media_type(event, "voice")
        elif action == "history_toggle_document":
            await handle_toggle_media_type(event, "document")
        elif action.startswith("set_history_delay"):
            try:
                seconds = int(extra_data[0]) if extra_data else 0
                from handlers.button.session_management import session_manager

                await session_manager.set_history_delay(event.chat_id, seconds)
                # 设置后回到控制器的延迟设置页，保持返回路径正确
                try:
                    from controllers.menu_controller import menu_controller

                    await menu_controller.show_history_delay_settings(event)
                except Exception:
                    await new_menu_system.show_history_delay_settings(event)
            except Exception as e:
                logger.error(f"设置历史延迟失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "current_history_task":
            await new_menu_system.show_current_history_task(event)
        elif action == "pause_history":
            from handlers.button.session_management import session_manager

            ok = await session_manager.pause_history_task(event.chat_id)
            await event.answer("⏸️ 已暂停" if ok else "❌ 暂停失败")
            await new_menu_system.show_history_messages(event)
        elif action == "resume_history":
            from handlers.button.session_management import session_manager

            ok = await session_manager.resume_history_task(event.chat_id)
            await event.answer("▶️ 已恢复" if ok else "❌ 恢复失败")
            await new_menu_system.show_history_messages(event)
        elif action == "stop_history":
            from handlers.button.session_management import session_manager

            ok = await session_manager.stop_history_task(event.chat_id)
            await event.answer("⏹️ 已停止" if ok else "❌ 停止失败")
            await new_menu_system.show_history_messages(event)
        elif action == "save_time_setting":
            try:
                await event.answer("✅ 时间设置已保存")
                # 返回到历史时间范围选择页面（新架构控制器）
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_time_range(event)
            except Exception as e:
                logger.error(f"保存时间设置失败: {str(e)}")
                await event.answer("保存失败", alert=True)
        # 媒体设置相关菜单
        elif action == "media_types":
            await new_menu_system.show_media_types(event)
        elif action == "media_size_settings":
            await new_menu_system.show_media_size_settings(event)
        elif action == "media_duration_settings":
            await new_menu_system.show_media_duration_settings(event)
        elif action == "open_duration_picker":
            # 进入指定分量的全屏 Picker（天/时/分/秒）并在确认后立即保存
            try:
                side = extra_data[0] if len(extra_data) > 0 else "min"  # min|max
                unit = (
                    extra_data[1] if len(extra_data) > 1 else "days"
                )  # days|hours|minutes|seconds
                await new_menu_system.show_single_unit_duration_picker(
                    event, side, unit
                )
            except Exception as e:
                logger.error(f"打开分量选择器失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "media_extension_settings":
            await new_menu_system.show_media_extension_settings(event)
        # 媒体设置相关的切换操作
        elif action == "toggle_allow_text":
            await handle_toggle_setting(event, "allow_text")
        elif action == "toggle_media_extension":
            await handle_toggle_setting(event, "media_extension_enabled")
        elif action == "toggle_extension_mode":
            await handle_toggle_extension_mode(event)
        elif action == "toggle_image":
            await handle_toggle_media_type(event, "image")
        elif action == "toggle_video":
            await handle_toggle_media_type(event, "video")
        elif action == "toggle_music":
            await handle_toggle_media_type(event, "audio")
        elif action == "toggle_voice":
            await handle_toggle_media_type(event, "voice")
        elif action == "toggle_document":
            await handle_toggle_media_type(event, "document")
        elif action == "toggle_media_duration":
            await handle_toggle_media_duration(event)
        elif action == "set_duration_range":
            # 打开双行区间总览（保持兼容旧入口）
            await new_menu_system.show_media_duration_settings(event)
        elif action == "set_duration_start":
            # 兼容旧逻辑：直接进入起始行的四段选择
            await new_menu_system.show_duration_range_picker(event, "min")
        elif action == "set_duration_end":
            # 兼容旧逻辑：直接进入结束行的四段选择
            await new_menu_system.show_duration_range_picker(event, "max")
        elif action == "save_duration_settings":
            await handle_save_duration_settings(event)
        elif action == "set_duration_component":
            try:
                side = extra_data[0]
                unit = extra_data[1]
                value = int(extra_data[2])
                from ..forward_management import forward_manager

                ok = await forward_manager.set_duration_component(side, unit, value)
                if not ok:
                    await event.answer("保存失败", alert=True)
                else:
                    await event.answer("✓ 已保存")
                # 保存后自动返回上一页并刷新主段显示
                await new_menu_system.show_media_duration_settings(event)
            except Exception as e:
                logger.error(f"设置时长分量失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "select_duration_value":
            # 单纯更新选择的当前高亮值，不落库
            try:
                side = extra_data[0]
                unit = extra_data[1]
                value = int(extra_data[2])
                await new_menu_system.show_single_unit_duration_picker(
                    event, side, unit, selected_value=value
                )
            except Exception as e:
                logger.error(f"选择时长值失败: {str(e)}")
                await event.answer("操作失败", alert=True)

        elif action == "confirm_duration_value":
            # 确认保存当前值，落库并返回
            try:
                side = extra_data[0]
                unit = extra_data[1]
                value = int(extra_data[2])
                from ..forward_management import forward_manager

                ok = await forward_manager.set_duration_component(side, unit, value)
                if ok:
                    await event.answer("✓ 已保存")
                else:
                    await event.answer("保存失败", alert=True)
                await new_menu_system.show_media_duration_settings(event)
            except Exception as e:
                logger.error(f"确认保存时长值失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        # 媒体大小相关操作
        elif action == "toggle_media_size_filter":
            await handle_toggle_media_size_filter(event)
        elif action == "toggle_media_size_alert":
            await handle_toggle_media_size_alert(event)
        elif action == "toggle_ext":
            # 切换某个扩展名选中状态（服务层）
            try:
                ext = extra_data[0] if extra_data else ""
                from services.forward_settings_service import forward_settings_service

                new_state = await forward_settings_service.toggle_media_extension(ext)
                await event.answer(f"{ext} 已{'选中' if new_state else '取消'}")
                await new_menu_system.show_media_extension_settings(event)
            except Exception as e:
                logger.error(f"切换扩展名失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "set_media_size_limit":
            # 进入一个简单的预设选择（基于旧菜单的可选值），后续可扩展为输入
            from ..forward_management import forward_manager

            settings = await forward_manager.get_global_media_settings()
            current = settings.get("media_size_limit", 100)
            # 快捷选项
            options = [10, 20, 50, 100, 200, 500]
            buttons = []
            row = []
            for val in options:
                row.append(
                    Button.inline(
                        f"{val}MB{' ✅' if val == current else ''}",
                        f"new_menu:confirm_media_size_limit:{val}",
                    )
                )
                if len(row) == 3:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append(
                [Button.inline("👈 返回上一级", "new_menu:media_size_settings")]
            )
            # 添加时间戳避免内容重复
            from datetime import datetime

            timestamp = datetime.now().strftime("%H:%M:%S")
            text = f"请选择媒体大小限制：\n\n更新时间: {timestamp}"
            await event.edit(text, buttons=buttons)
        elif action == "confirm_media_size_limit":
            try:
                val = int(extra_data[0]) if extra_data else 100
                from ..forward_management import forward_manager

                ok = await forward_manager.set_media_size_limit(val)
                if ok:
                    await event.answer("已更新媒体大小限制")
                else:
                    await event.answer("更新失败", alert=True)
                await new_menu_system.show_media_size_settings(event)
            except Exception as e:
                logger.error(f"确认媒体大小失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "forward_analytics":
            await new_menu_system.show_forward_analytics(event)
        elif action == "anomaly_detection":
            await new_menu_system.show_anomaly_detection(event)
        elif action == "realtime_monitor":
            await new_menu_system.show_realtime_monitor(event)
        elif action == "detailed_analytics":
            await new_menu_system.show_detailed_analytics(event)
        elif action == "performance_analysis":
            await new_menu_system.show_performance_analysis(event)
        elif action == "failure_analysis":
            await new_menu_system.show_failure_analysis(event)
        elif action == "export_report":
            await new_menu_system.export_report(event)
        elif action == "export_csv":
            await new_menu_system.export_csv(event)

        # 智能去重设置回调
        elif action == "smart_dedup_settings":
            await new_menu_system.show_smart_dedup_settings(event)
        elif action == "dedup_time_window":
            await new_menu_system.show_dedup_time_window(event)
        elif action == "dedup_similarity":
            await new_menu_system.show_dedup_similarity(event)
        elif action == "dedup_content_hash":
            await new_menu_system.show_dedup_content_hash(event)
        elif action == "dedup_video":
            await new_menu_system.show_dedup_video(event)
        elif action == "dedup_statistics":
            await new_menu_system.show_dedup_statistics(event)
        elif action == "dedup_advanced":
            await new_menu_system.show_dedup_advanced(event)

        # 智能去重配置更新 - 使用新的控制器架构
        elif action == "toggle_time_window":
            try:
                from controllers.menu_controller import menu_controller

                enabled = extra_data[0].lower() == "true" if extra_data else True
                await menu_controller.toggle_time_window(event, enabled)
            except Exception as e:
                logger.error(f"切换时间窗口失败: {e}")
                await handle_toggle_time_window(event, extra_data)  # 降级到旧方法
        elif action == "set_time_window":
            try:
                from controllers.menu_controller import menu_controller

                hours = int(extra_data[0]) if extra_data else 24
                await menu_controller.set_time_window(event, hours)
            except Exception as e:
                logger.error(f"设置时间窗口失败: {e}")
                await handle_set_time_window(event, extra_data)  # 降级到旧方法
        elif action == "set_similarity":
            try:
                from controllers.menu_controller import menu_controller

                threshold = float(extra_data[0]) if extra_data else 0.85
                await menu_controller.set_similarity_threshold(event, threshold)
            except Exception as e:
                logger.error(f"设置相似度失败: {e}")
                await handle_set_similarity(event, extra_data)  # 降级到旧方法
        elif action == "manual_cleanup":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.manual_cleanup_cache(event)
            except Exception as e:
                logger.error(f"手动清理失败: {e}")
                await handle_manual_cleanup(event)  # 降级到旧方法
        elif action == "toggle_similarity":
            await handle_toggle_similarity(event, extra_data)
        elif action == "toggle_content_hash":
            await handle_toggle_content_hash(event, extra_data)
        elif action == "toggle_video_file_id":
            await handle_toggle_video_file_id(event, extra_data)
        elif action == "toggle_video_partial":
            await handle_toggle_video_partial(event, extra_data)
        elif action == "set_video_partial_bytes":
            await handle_set_video_partial_bytes(event, extra_data)
        elif action == "set_cleanup_interval":
            await handle_set_cleanup_interval(event, extra_data)
        elif action == "reset_dedup_config":
            await handle_reset_dedup_config(event)
        elif action == "dedup_clear_cache":
            await handle_clear_dedup_cache(event)
        elif action == "dedup_hash_examples":
            await new_menu_system.show_dedup_hash_examples(event)

        # 四大功能中心 - 使用新的控制器架构
        elif action == "forward_hub":
            await new_menu_system.show_forward_hub(event)
        elif action == "dedup_hub":
            await new_menu_system.show_dedup_hub(event)
        elif action == "analytics_hub":
            await new_menu_system.show_analytics_hub(event)
        elif action == "system_hub":
            # 先即时应答，避免“处理中”卡住
            try:
                await event.answer("正在打开系统设置中心…")
            except Exception:
                pass
            await new_menu_system.show_system_hub(event)
        elif action == "db_archive_once":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.run_db_archive_once(event)
            except Exception as e:
                logger.error(f"手动归档失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "db_archive_force":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.run_db_archive_force(event)
            except Exception as e:
                logger.error(f"强制归档失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "rebuild_bloom":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.rebuild_bloom_index(event)
            except Exception as e:
                logger.error(f"重建 Bloom 索引失败: {str(e)}")
                await event.answer("操作失败", alert=True)
        elif action == "help_guide":
            await new_menu_system.show_help_guide(event)

        # 数据库性能监控
        elif action == "db_performance_monitor":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_db_performance_monitor(event)
            except Exception as e:
                logger.error(f"显示数据库性能监控失败: {str(e)}")
                await event.answer("加载监控面板失败", alert=True)
        elif action == "db_optimization_center":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_db_optimization_center(event)
            except Exception as e:
                logger.error(f"显示数据库优化中心失败: {str(e)}")
                await event.answer("加载优化中心失败", alert=True)
        elif action == "enable_db_optimization":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.enable_db_optimization(event)
            except Exception as e:
                logger.error(f"启用数据库优化失败: {str(e)}")
                await event.answer("启用优化失败", alert=True)
        elif action == "run_db_optimization_check":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.run_db_optimization_check(event)
            except Exception as e:
                logger.error(f"运行优化检查失败: {str(e)}")
                await event.answer("运行检查失败", alert=True)
        elif action == "db_performance_refresh":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.refresh_db_performance(event)
            except Exception as e:
                logger.error(f"刷新性能数据失败: {str(e)}")
                await event.answer("刷新数据失败", alert=True)
        elif action == "db_optimization_refresh":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.refresh_db_optimization_status(event)
            except Exception as e:
                logger.error(f"刷新优化状态失败: {str(e)}")
                await event.answer("刷新状态失败", alert=True)

        # 数据库监控子功能（占位符实现）
        elif action in [
            "db_query_analysis",
            "db_performance_trends",
            "db_alert_management",
            "db_optimization_advice",
            "db_detailed_report",
            "db_performance_report",
            "db_optimization_config",
            "db_index_analysis",
            "db_cache_management",
            "db_optimization_logs",
        ]:
            try:
                # 临时显示功能开发中
                await event.answer(
                    "⚠️ 该功能正在开发中，敬请期待！\n\n🔧 当前可用功能：\n• 数据库监控面板\n• 优化系统启用\n• 性能检查运行",
                    alert=True,
                )
            except Exception as e:
                logger.error(f"处理数据库监控子功能失败: {str(e)}")
                await event.answer("功能暂不可用", alert=True)

        # 新架构 - 规则管理
        elif action == "rule_statistics":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_rule_statistics(event)
            except Exception as e:
                logger.error(f"规则统计失败: {e}")
                await event.answer("加载规则统计失败", alert=True)
        elif action == "edit_rule" and extra_data:
            try:
                from controllers.menu_controller import menu_controller

                rule_id = int(extra_data[0])
                await menu_controller.show_rule_detail(event, rule_id)
            except Exception as e:
                logger.error(f"显示规则详情失败: {e}")
                await event.answer("加载规则详情失败", alert=True)
        elif action.startswith("manage_multi_source:"):
            # 进入多源管理详细页（现有老/新混合实现）
            try:
                rid = int(action.split(":")[1]) if ":" in action else None
                if rid is None:
                    raise ValueError("规则ID缺失")
                await new_menu_system.show_multi_source_detail(event, rid)
            except Exception as e:
                logger.error(f"进入多源管理失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "edit_rule_settings" and extra_data:
            # 打开老菜单的详细设置页（完整开关与配置）
            try:
                rule_id = int(extra_data[0])
                await new_menu_system.show_rule_detail_settings(event, rule_id)
            except Exception as e:
                logger.error(f"进入规则编辑失败: {e}")
                await event.answer("加载规则设置失败", alert=True)
        elif action == "edit_rule_settings":
            # 无参数时进入规则选择后打开设置页
            try:
                await new_menu_system.show_rule_selection_for_settings(event)
            except Exception as e:
                logger.error(f"打开规则设置选择失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "manage_keywords" and extra_data:
            # 跳转到独立的管理关键词页面
            try:
                from controllers.menu_controller import menu_controller

                rid = int(extra_data[0])
                await menu_controller.show_manage_keywords(event, rid)
            except Exception as e:
                logger.error(f"进入关键词管理失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action.startswith("manage_keywords:"):
            try:
                from controllers.menu_controller import menu_controller

                rid = int(action.split(":")[1])
                await menu_controller.show_manage_keywords(event, rid)
            except Exception as e:
                logger.error(f"进入关键词管理失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "manage_replace_rules" and extra_data:
            # 跳转到独立的管理替换规则页面
            try:
                from controllers.menu_controller import menu_controller

                rid = int(extra_data[0])
                await menu_controller.show_manage_replace_rules(event, rid)
            except Exception as e:
                logger.error(f"进入替换规则管理失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action.startswith("manage_replace_rules:"):
            try:
                from controllers.menu_controller import menu_controller

                rid = int(action.split(":")[1])
                await menu_controller.show_manage_replace_rules(event, rid)
            except Exception as e:
                logger.error(f"进入替换规则管理失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action.startswith("kw_add:") or action == "kw_add":
            # new_menu:kw_add:<rule_id>
            try:
                from controllers.menu_controller import menu_controller

                rid = int((extra_data[0] if extra_data else action.split(":")[1]))
                # 进入添加关键词模式
                user_id = event.chat_id
                chat_id = event.chat_id
                msg = await event.get_message()
                # 使用 session_manager 替代 state_manager
                from handlers.button.session_management import session_manager

                if user_id not in session_manager.user_sessions:
                    session_manager.user_sessions[user_id] = {}
                session_manager.user_sessions[user_id][chat_id] = {
                    "state": f"kw_add:{rid}",
                    "message": msg,
                    "state_type": "keyword",
                }
                await event.respond(
                    "请逐行发送要添加的关键词（支持多行），发送完成后无需额外操作"
                )
                await menu_controller.show_manage_keywords(event, rid)
            except Exception as e:
                logger.error(f"进入添加关键词失败: {e}")
                await event.answer("操作失败", alert=True)
        elif action.startswith("kw_delete:") or action == "kw_delete":
            # new_menu:kw_delete:<rule_id>
            try:
                from controllers.menu_controller import menu_controller

                rid = int((extra_data[0] if extra_data else action.split(":")[1]))
                user_id = event.chat_id
                chat_id = event.chat_id
                msg = await event.get_message()
                # 使用 session_manager 替代 state_manager
                from handlers.button.session_management import session_manager

                if user_id not in session_manager.user_sessions:
                    session_manager.user_sessions[user_id] = {}
                session_manager.user_sessions[user_id][chat_id] = {
                    "state": f"kw_delete:{rid}",
                    "message": msg,
                    "state_type": "keyword",
                }
                await event.respond(
                    "请发送要删除的关键词序号（支持空格/逗号分隔），例如: 1 3 5"
                )
                await menu_controller.show_manage_keywords(event, rid)
            except Exception as e:
                logger.error(f"进入删除关键词失败: {e}")
                await event.answer("操作失败", alert=True)
        elif action.startswith("rr_add:") or action == "rr_add":
            # new_menu:rr_add:<rule_id>
            try:
                from controllers.menu_controller import menu_controller

                rid = int((extra_data[0] if extra_data else action.split(":")[1]))
                user_id = event.chat_id
                chat_id = event.chat_id
                msg = await event.get_message()
                # 使用 session_manager 替代 state_manager
                from handlers.button.session_management import session_manager

                if user_id not in session_manager.user_sessions:
                    session_manager.user_sessions[user_id] = {}
                session_manager.user_sessions[user_id][chat_id] = {
                    "state": f"rr_add:{rid}",
                    "message": msg,
                    "state_type": "replace",
                }
                await event.respond(
                    "请按每行一条格式发送：pattern => replacement（也支持空格分隔）"
                )
                await menu_controller.show_manage_replace_rules(event, rid)
            except Exception as e:
                logger.error(f"进入新增替换规则失败: {e}")
                await event.answer("操作失败", alert=True)
        elif action.startswith("rr_delete:") or action == "rr_delete":
            # new_menu:rr_delete:<rule_id>
            try:
                from controllers.menu_controller import menu_controller

                rid = int((extra_data[0] if extra_data else action.split(":")[1]))
                user_id = event.chat_id
                chat_id = event.chat_id
                msg = await event.get_message()
                # 使用 session_manager 替代 state_manager
                from handlers.button.session_management import session_manager

                if user_id not in session_manager.user_sessions:
                    session_manager.user_sessions[user_id] = {}
                session_manager.user_sessions[user_id][chat_id] = {
                    "state": f"rr_delete:{rid}",
                    "message": msg,
                    "state_type": "replace",
                }
                await event.respond(
                    "请发送要删除的替换规则序号（支持空格/逗号分隔），例如: 2 4 7"
                )
                await menu_controller.show_manage_replace_rules(event, rid)
            except Exception as e:
                logger.error(f"进入删除替换规则失败: {e}")
                await event.answer("操作失败", alert=True)
        elif action == "rule_stats" and extra_data:
            # 单规则统计占位：暂时跳规则详情
            try:
                from controllers.menu_controller import menu_controller

                rid = int(extra_data[0])
                await menu_controller.show_rule_detail(event, rid)
            except Exception as e:
                logger.error(f"进入规则统计失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action.startswith("rule_stats:"):
            # 单规则统计占位：暂时跳规则详情
            try:
                from controllers.menu_controller import menu_controller

                rid = int(action.split(":")[1])
                await menu_controller.show_rule_detail(event, rid)
            except Exception as e:
                logger.error(f"进入规则统计失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "create_rule":
            # 创建规则入口占位：暂时回到规则列表
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_rule_list(event)
            except Exception as e:
                logger.error(f"创建规则入口失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "search_rules":
            # 搜索入口占位：暂时回到规则列表
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_rule_list(event)
            except Exception as e:
                logger.error(f"搜索规则入口失败: {e}")
                await event.answer("加载失败", alert=True)
        elif action == "rule_list_page" and extra_data:
            try:
                from controllers.menu_controller import menu_controller

                page = int(extra_data[0])
                await menu_controller.show_rule_list(event, page)
            except Exception as e:
                logger.error(f"翻页失败: {e}")
                await event.answer("翻页失败", alert=True)
        elif action == "toggle_rule_status" and extra_data:
            try:
                from controllers.menu_controller import menu_controller

                rule_id = int(extra_data[0])
                enabled = (
                    extra_data[1].lower() == "true" if len(extra_data) > 1 else True
                )
                await menu_controller.toggle_rule_status(event, rule_id, enabled)
            except Exception as e:
                logger.error(f"切换规则状态失败: {e}")
                await event.answer("操作失败", alert=True)
        elif action == "delete_rule_confirm" and extra_data:
            try:
                rule_id = int(extra_data[0])
                await event.answer(f"确认删除规则 {rule_id}？", alert=True)
                # 这里可以添加确认对话框逻辑
            except Exception as e:
                logger.error(f"删除确认失败: {e}")

        # 新架构 - 性能监控
        elif action == "realtime_monitor":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_realtime_monitor(event)
            except Exception as e:
                logger.error(f"实时监控失败: {e}")
                await event.answer("加载实时监控失败", alert=True)

        # 新架构 - 会话管理 (历史消息)
        elif action == "history_task_selector":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_history_task_selector(event)
            except Exception as e:
                logger.error(f"历史任务选择失败: {e}")
                await event.answer("加载历史任务选择失败", alert=True)
        elif action == "toggle_history_dedup":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.toggle_history_dedup(event)
            except Exception as e:
                logger.error(f"切换历史去重失败: {e}")
                await event.answer("操作失败", alert=True)
        elif action == "current_history_task":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_current_history_task(event)
            except Exception as e:
                logger.error(f"历史任务状态失败: {e}")
                await event.answer("加载历史任务状态失败", alert=True)
        elif action == "select_history_rule" and extra_data:
            try:
                from controllers.menu_controller import menu_controller

                rule_id = int(extra_data[0])
                await menu_controller.select_history_rule(event, rule_id)
            except Exception as e:
                logger.error(f"选择历史规则失败: {e}")
                await event.answer("选择失败", alert=True)
        # 注意：上方已由模块 history_module 处理 history_time_range，避免重复入口
        # 注意：避免重复定义 history_delay_settings，已上方处理
        elif action == "set_time_range_all":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.set_time_range_all(event)
            except Exception as e:
                logger.error(f"设置全部时间失败: {e}")
                await event.answer("设置失败", alert=True)
        elif action == "set_time_range_days" and extra_data:
            try:
                from controllers.menu_controller import menu_controller

                days = int(extra_data[0])
                await menu_controller.set_time_range_days(event, days)
            except Exception as e:
                logger.error(f"设置时间范围失败: {e}")
                await event.answer("设置失败", alert=True)
        elif action == "set_delay" and extra_data:
            try:
                from controllers.menu_controller import menu_controller

                delay_seconds = int(extra_data[0])
                await menu_controller.set_delay(event, delay_seconds)
            except Exception as e:
                logger.error(f"设置延迟失败: {e}")
                await event.answer("设置失败", alert=True)
        elif action == "start_history_task":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.start_history_task(event)
            except Exception as e:
                logger.error(f"启动历史任务失败: {e}", exc_info=True)
                await event.answer(f"启动失败: {str(e)}", alert=True)
        elif action == "cancel_history_task":
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.cancel_history_task(event)
            except Exception as e:
                logger.error(f"取消历史任务失败: {e}")
                await event.answer("取消失败", alert=True)
        elif action == "cleanup_history_tasks":
            try:
                from handlers.button.session_management import session_manager

                cleaned_count = await session_manager.cleanup_completed_tasks(
                    event.chat_id
                )
                if cleaned_count > 0:
                    await event.answer(f"✅ 已清理 {cleaned_count} 个已完成的任务状态")
                else:
                    await event.answer("ℹ️ 没有需要清理的任务状态")
                # 刷新当前任务页面
                from controllers.menu_controller import menu_controller

                await menu_controller.show_current_history_task(event)
            except Exception as e:
                logger.error(f"清理历史任务状态失败: {e}")
                await event.answer("清理失败", alert=True)

        # 兼容旧的智能去重设置入口
        elif action == "smart_dedup_settings":
            await new_menu_system.show_dedup_hub(event)

        # 新增的快捷功能（暂时开发中）
        elif action == "forward_search":
            await new_menu_system.show_forward_search(event)
        elif action == "dedup_cache_management":
            await new_menu_system.show_dedup_cache_management(event)
        elif action == "system_status":
            await new_menu_system.show_system_status(event)
        elif action == "log_viewer":
            await new_menu_system.show_log_viewer(event)
        elif action == "version_info":
            await new_menu_system.show_version_info(event)
        elif action == "refresh_main_menu":
            # 刷新主菜单数据
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_main_menu(event, force_refresh=True)
                await event.answer("✅ 数据已刷新")
            except Exception as e:
                logger.error(f"刷新主菜单失败: {e}")
                await event.answer("❌ 刷新失败，请重试", alert=True)
        elif action == "refresh_forward_hub":
            # 刷新转发中心数据
            try:
                from controllers.menu_controller import menu_controller

                await menu_controller.show_forward_hub(event, force_refresh=True)
                await event.answer("✅ 转发中心数据已刷新")
            except Exception as e:
                logger.error(f"刷新转发中心失败: {e}")
                await event.answer("❌ 刷新失败，请重试", alert=True)
        elif action == "exit":
            await event.delete()
            await event.answer("已退出菜单")
        else:
            logger.warning(f"未知的新菜单动作: action={action}, data={data}")
            try:
                await event.answer(f"未知操作: {action}")
            except Exception:
                pass

        # 标记回调已处理
        if not action == "exit":
            await event.answer()

    except Exception as e:
        logger.error(f"处理新菜单回调时出错: {str(e)}")
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        await event.answer("处理请求时出错，请检查日志")


# ========== 智能去重配置处理函数 ===========
async def handle_toggle_time_window(event, extra_data):
    """切换时间窗口去重开关"""
    try:
        from services.dedup.engine import smart_deduplicator

        enable = extra_data[0].lower() == "true" if extra_data else True
        smart_deduplicator.update_config({"enable_time_window": enable})

        await event.answer(f"时间窗口去重已{'开启' if enable else '关闭'}")
        await new_menu_system.show_dedup_time_window(event)

    except Exception as e:
        logger.error(f"切换时间窗口设置失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_set_time_window(event, extra_data):
    """设置时间窗口大小"""
    try:
        from services.dedup.engine import smart_deduplicator

        hours = int(extra_data[0]) if extra_data else 24
        smart_deduplicator.update_config({"time_window_hours": hours})

        await event.answer(f"时间窗口已设置为 {hours} 小时")
        await new_menu_system.show_dedup_time_window(event)

    except Exception as e:
        logger.error(f"设置时间窗口失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_toggle_similarity(event, extra_data):
    """切换相似度检测开关"""
    try:
        from services.dedup.engine import smart_deduplicator

        enable = extra_data[0].lower() == "true" if extra_data else True
        smart_deduplicator.update_config({"enable_smart_similarity": enable})

        await event.answer(f"智能相似度检测已{'开启' if enable else '关闭'}")
        await new_menu_system.show_dedup_similarity(event)

    except Exception as e:
        logger.error(f"切换相似度设置失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_set_similarity(event, extra_data):
    """设置相似度阈值"""
    try:
        from services.dedup.engine import smart_deduplicator

        threshold = float(extra_data[0]) if extra_data else 0.85
        smart_deduplicator.update_config({"similarity_threshold": threshold})

        await event.answer(f"相似度阈值已设置为 {threshold:.0%}")
        await new_menu_system.show_dedup_similarity(event)

    except Exception as e:
        logger.error(f"设置相似度阈值失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_toggle_content_hash(event, extra_data):
    """切换内容哈希去重开关"""
    try:
        from services.dedup.engine import smart_deduplicator

        enable = extra_data[0].lower() == "true" if extra_data else True
        smart_deduplicator.update_config({"enable_content_hash": enable})

        await event.answer(f"内容哈希去重已{'开启' if enable else '关闭'}")
        await new_menu_system.show_dedup_content_hash(event)

    except Exception as e:
        logger.error(f"切换内容哈希设置失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_set_cleanup_interval(event, extra_data):
    """设置缓存清理间隔"""
    try:
        from services.dedup.engine import smart_deduplicator

        interval = int(extra_data[0]) if extra_data else 3600
        smart_deduplicator.update_config({"cache_cleanup_interval": interval})

        await event.answer(f"清理间隔已设置为 {interval // 60} 分钟")
        await new_menu_system.show_dedup_advanced(event)

    except Exception as e:
        logger.error(f"设置清理间隔失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_toggle_video_file_id(event, extra_data):
    """切换视频 file_id 判重开关"""
    try:
        from services.dedup.engine import smart_deduplicator

        enable = extra_data[0].lower() == "true" if extra_data else True
        smart_deduplicator.update_config({"enable_video_file_id_check": enable})
        await event.answer(f"视频 file_id 判重已{'开启' if enable else '关闭'}")
        await new_menu_system.show_dedup_video(event)
    except Exception as e:
        logger.error(f"切换视频 file_id 判重失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_toggle_video_partial(event, extra_data):
    """切换视频部分哈希判重开关"""
    try:
        from services.dedup.engine import smart_deduplicator

        enable = extra_data[0].lower() == "true" if extra_data else True
        smart_deduplicator.update_config({"enable_video_partial_hash_check": enable})
        await event.answer(f"视频部分哈希判重已{'开启' if enable else '关闭'}")
        await new_menu_system.show_dedup_video(event)
    except Exception as e:
        logger.error(f"切换视频部分哈希失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_set_video_partial_bytes(event, extra_data):
    """设置视频部分哈希采样字节数"""
    try:
        from services.dedup.engine import smart_deduplicator

        part_bytes = int(extra_data[0]) if extra_data else 262144
        if part_bytes < 65536:
            part_bytes = 65536
        smart_deduplicator.update_config({"video_partial_hash_bytes": part_bytes})
        await event.answer(f"采样字节已设置为 {part_bytes // 1024} KB")
        await new_menu_system.show_dedup_video(event)
    except Exception as e:
        logger.error(f"设置视频部分哈希字节失败: {e}")
        await event.answer("设置失败", alert=True)


async def handle_manual_cleanup(event):
    """手动清理缓存"""
    try:
        from services.dedup.engine import smart_deduplicator

        # 强制清理缓存
        smart_deduplicator.last_cleanup = 0  # 重置清理时间强制触发
        await smart_deduplicator._cleanup_cache_if_needed()

        stats = smart_deduplicator.get_stats()
        await event.answer(
            f"缓存已清理完成\n剩余: {stats.get('cached_signatures', 0)} 签名, {stats.get('cached_content_hashes', 0)} 哈希",
            alert=True,
        )
        await new_menu_system.show_dedup_advanced(event)

    except Exception as e:
        logger.error(f"手动清理失败: {e}")
        await event.answer("清理失败", alert=True)


async def handle_reset_dedup_config(event):
    """重置去重配置"""
    try:
        from services.dedup.engine import smart_deduplicator

        # 使用内置的重置方法
        smart_deduplicator.reset_to_defaults()

        await event.answer("配置已重置为默认值", alert=True)
        await new_menu_system.show_smart_dedup_settings(event)

    except Exception as e:
        logger.error(f"重置配置失败: {e}")
        await event.answer("重置失败", alert=True)


async def handle_clear_dedup_cache(event):
    """清理去重缓存"""
    try:
        from services.dedup.engine import smart_deduplicator

        # 清空所有缓存
        smart_deduplicator.time_window_cache.clear()
        smart_deduplicator.content_hash_cache.clear()

        await event.answer("所有去重缓存已清理", alert=True)
        await new_menu_system.show_smart_dedup_settings(event)

    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        await event.answer("清理失败", alert=True)
