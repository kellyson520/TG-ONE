import traceback
import logging
from telethon import Button

from core.container import container
from handlers.button.settings_manager import get_media_settings_text

from handlers.button.button_helpers import (
    create_media_extensions_buttons,
    create_media_settings_buttons,
    create_media_size_buttons,
    create_media_types_buttons,
)

logger = logging.getLogger(__name__)


async def handle_media_callback(event, **kwargs):
    """处理媒体设置相关回调 (异步版) - Refactored to use Strategy Registry"""
    try:
        data = event.data.decode("utf-8")
        parts = data.split(":")
        action = parts[0]

        from handlers.button.strategies import MenuHandlerRegistry
        
        if await MenuHandlerRegistry.dispatch(event, action, data=data, **kwargs):
            return
            
        logger.warning(f"MediaCallback: No strategy found for action {action}")
        await event.answer("⚠️ 未知指令", alert=True)

    except Exception as e:
        logger.error(f"处理媒体回调失败: {e}", exc_info=True)
        await event.answer("⚠️ 系统繁忙", alert=True)


async def _show_rule_media_settings(event, rule_id, session=None):
    """显示规则的媒体设置页面 (内部辅助函数)"""
    try:
        rule = await container.rule_repo.get_by_id(int(rule_id))
        if rule:
            await event.edit(
                await get_media_settings_text(),
                buttons=await create_media_settings_buttons(rule),
            )
        else:
            await event.answer("❌ 规则不存在", alert=True)
    except Exception as e:
        logger.error(f"显示媒体设置失败: {e}", exc_info=True)
        await event.answer("⚠️ 加载失败", alert=True)


async def callback_media_settings(event, rule_id, session, message, data):
    # 显示媒体设置页面
    await _show_rule_media_settings(event, rule_id, session)
    return


async def callback_set_max_media_size(event, rule_id, session, message, data):
    await event.edit(
        "请选择最大媒体大小(MB)：",
        buttons=await create_media_size_buttons(rule_id, page=0),
    )
    return


async def callback_select_max_media_size(event, rule_id, session, message, data):
    parts = data.split(":", 2)
    if len(parts) == 3:
        _, rule_id, size = parts
        logger.info(f"设置规则 {rule_id} 的最大媒体大小为: {size}")
        try:
            # 使用 Service 层处理更新和同步
            res = await container.rule_service.toggle_rule_setting(int(rule_id), "max_media_size", int(size))
            
            if res.get("success"):
                rule = await container.rule_repo.get_by_id(int(rule_id))
                await event.edit(
                    "媒体设置：", buttons=await create_media_settings_buttons(rule)
                )
                await event.answer(f"已设置最大媒体大小为: {size}MB")
                logger.info("界面更新完成")
            else:
                await event.answer(f"❌ 更新失败: {res.get('error')}")
        except Exception as e:
            logger.error(f"设置最大媒体大小时出错: {str(e)}", exc_info=True)
            await event.answer("⚠️ 设置失败")
    return


async def callback_set_media_types(event, rule_id, session, message, data):
    """处理查看并设置媒体类型的回调"""
    try:
        # 获取屏蔽状态
        _, _, media_types = await container.rule_repo.get_media_types(None, int(rule_id))

        if not media_types:
            await event.answer("获取媒体类型设置失败")
            return

        await event.edit(
            "请选择要屏蔽的媒体类型",
            buttons=await create_media_types_buttons(int(rule_id), media_types),
        )
    except Exception as e:
        logger.error(f"设置媒体类型时出错: {str(e)}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return


async def callback_toggle_media_type(event, rule_id, session, message, data):
    """处理切换媒体类型的回调"""
    parts = data.split(":")
    if len(parts) < 3:
        await event.answer("数据格式错误")
        return

    rule_id_val = parts[1]
    media_type = parts[2]
    
    try:
        # 使用 Service 处理切换和同步
        res = await container.rule_service.toggle_media_type(int(rule_id_val), media_type)
        
        if res.get("success"):
            # 重新获取状态更新界面
            _, _, media_types = await container.rule_repo.get_media_types(None, int(rule_id_val))
            await event.edit(
                "请选择要屏蔽的媒体类型",
                buttons=await create_media_types_buttons(int(rule_id_val), media_types),
            )
            status = "已屏蔽" if res.get("new_status") else "已放行"
            await event.answer(f"{media_type} {status}")
        else:
            await event.answer(f"❌ 切换失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"切换媒体类型出错: {e}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return


async def callback_size_page(event, rule_id, session, message, data):
    parts = data.split(":")
    if len(parts) >= 3:
        _, rule_id, page = parts[:3]
        await event.edit(
            "请选择最大媒体大小(MB)：",
            buttons=await create_media_size_buttons(rule_id, page=int(page)),
        )
    return


async def callback_set_media_extensions(event, rule_id, session, message, data):
    await event.edit(
        "请选择要过滤的媒体扩展名：",
        buttons=await create_media_extensions_buttons(int(rule_id), page=0),
    )
    return


async def callback_media_extensions_page(event, rule_id, session, message, data):
    parts = data.split(":")
    if len(parts) >= 3:
        _, rule_id_str, page = parts[:3]
        await event.edit(
            "请选择要过滤的媒体扩展名：",
            buttons=await create_media_extensions_buttons(int(rule_id_str), page=int(page)),
        )
    return


async def callback_toggle_media_extension(event, rule_id, session, message, data):
    """处理切换媒体扩展名的回调"""
    parts = data.split(":")
    if len(parts) < 3:
        await event.answer("数据格式错误")
        return

    rule_id_val = parts[1]
    extension = parts[2]
    current_page = int(parts[3]) if len(parts) > 3 else 0

    try:
        # 使用 Service 切换并同步
        res = await container.rule_service.toggle_media_extension(int(rule_id_val), extension)
        
        if res.get("success"):
            await event.edit(
                "请选择要过滤的媒体扩展名：",
                buttons=await create_media_extensions_buttons(int(rule_id_val), page=current_page),
            )
            await event.answer(f"已更新扩展名: {extension}")
        else:
            await event.answer(f"❌ 更新失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"切换媒体扩展名出错: {e}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return


async def callback_toggle_media_allow_text(event, rule_id, session, message, data):
    """处理切换放行文本的回调"""
    try:
        # 使用 Service 处理通用布尔切换和同步
        res = await container.rule_service.toggle_rule_setting(int(rule_id), "media_allow_text")
        
        if res.get("success"):
            rule = await container.rule_repo.get_by_id(int(rule_id))
            await event.edit(
                await get_media_settings_text(),
                buttons=await create_media_settings_buttons(rule),
            )
            status = "开启" if res.get("new_value") else "关闭"
            await event.answer(f"已{status}放行文本")
        else:
            await event.answer(f"❌ 切换失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"切换放行文本失败: {e}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return
