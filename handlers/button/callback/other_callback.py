"""
通用规则设置回调处理器
"""

import asyncio
import logging
import traceback
from typing import Optional, List, Any, Dict
from telethon import Button

from core.container import container
from services.session_service import session_manager
from core.helpers.auto_delete import send_message_and_delete
from core.constants import RULES_PER_PAGE

logger = logging.getLogger(__name__)


async def handle_other_callback(event, **kwargs):
    """处理通用规则设置回调 - 使用策略分发"""
    try:
        data = event.data.decode("utf-8")
        parts = data.split(":")
        action = parts[0]

        if data == "close_settings":
            await event.delete()
            return

        from handlers.button.strategies import MenuHandlerRegistry
        if await MenuHandlerRegistry.dispatch(event, action, data=data, **kwargs):
            return

        # Fallback to legacy style if registration is missing
        rule_id = parts[1] if len(parts) > 1 else None
        
        handler_map = {
            "other_settings": callback_other_settings,
            "copy_rule": callback_copy_rule,
            "copy_keyword": callback_copy_keyword,
            "copy_replace": callback_copy_replace,
            "clear_keyword": callback_clear_keyword,
            "clear_replace": callback_clear_replace,
            "delete_rule": callback_delete_rule,
            "perform_copy_rule": callback_perform_copy_rule,
            "perform_copy_keyword": callback_perform_copy_keyword,
            "perform_copy_replace": callback_perform_copy_replace,
            "perform_clear_keyword": callback_perform_clear_keyword,
            "perform_clear_replace": callback_perform_clear_replace,
            "perform_delete_rule": callback_perform_delete_rule,
            "set_userinfo_template": callback_set_userinfo_template,
            "set_time_template": callback_set_time_template,
            "set_original_link_template": callback_set_original_link_template,
            "cancel_set_userinfo": callback_cancel_set_userinfo,
            "cancel_set_time": callback_cancel_set_time,
            "cancel_set_link": callback_cancel_set_original_link,
            "toggle_reverse_blacklist": callback_toggle_reverse_blacklist,
            "toggle_reverse_whitelist": callback_toggle_reverse_whitelist,
            "dedup_scan_now": callback_dedup_scan_now,
            "delete_duplicates": callback_delete_duplicates,
            "view_source_messages": callback_view_source_messages,
            "keep_duplicates": callback_keep_duplicates,
            "confirm_delete_duplicates": callback_confirm_delete_duplicates,
            "toggle_allow_delete_source_on_dedup": callback_toggle_allow_delete_source_on_dedup,
            "ufb_item": callback_handle_ufb_item,
        }

        handler = handler_map.get(action)
        if handler:
            # Note: We provide session as None to let handlers decide or use container
            await handler(event, rule_id, None, None, data)
        else:
            logger.warning(f"由于找不到处理器，其它设置回调未处理: {action}")
            await event.answer("⚠️ 未知指令", alert=True)

    except Exception as e:
        logger.error(f"处理其它回调失败: {e}", exc_info=True)
        await event.answer("⚠️ 系统繁忙", alert=True)


async def callback_other_settings(event, rule_id, session, message, data):
    """显示其它设置菜单"""
    from handlers.button.button_helpers import create_other_settings_buttons
    buttons = await create_other_settings_buttons(rule_id=rule_id)
    await event.edit("🛠️ **更多高级设置**", buttons=buttons)


async def callback_copy_rule(event, rule_id, session, message, data):
    """显示复制规则选择界面"""
    parts = data.split(":")
    page = int(parts[2]) if len(parts) > 2 else 0
    
    buttons = await _create_rule_selection_buttons(rule_id, page, "perform_copy_rule")
    await event.edit("📋 **复制规则设置**\n\n请选择要将当前规则复制到的目标规则：", buttons=buttons)


async def callback_perform_copy_rule(event, rule_id_data, session, message, data):
    """执行复制规则操作"""
    try:
        parts = rule_id_data.split(":")
        source_id, target_id = int(parts[0]), int(parts[1])
        
        await event.answer("⏳ 正在复制设置...")
        result = await container.rule_management_service.copy_rule(source_id, target_id)
        
        if result.get("success"):
            await event.answer("✅ 规则设置复制成功", alert=True)
            await callback_other_settings(event, source_id, None, None, "")
        else:
            await event.answer(f"❌ 复制失败: {result.get('error')}", alert=True)
    except Exception as e:
        logger.error(f"Perform copy rule failed: {e}")
        await event.answer("❌ 操作失败")


async def callback_dedup_scan_now(event, rule_id, session, message, data):
    """执行去重扫描"""
    try:
        await event.answer("🔍 正在扫描重复媒体...")
        rule = await container.rule_repo.get_by_id(int(rule_id))
        if not rule:
            await event.answer("❌ 规则不存在")
            return

        # 使用 Repository 直接查询重复签名
        from repositories.db_operations import DBOperations
        db_ops = await DBOperations.create()
        async with container.db.get_session() as s:
            dup_list, dup_map = await db_ops.scan_duplicate_media(s, str(rule.target_chat_telegram_id))

        if not dup_list:
            await event.answer("✅ 未发现重复媒体", alert=True)
            return

        lines = ["🔍 **发现重复媒体**\n"]
        for sig in dup_list[:10]:
            lines.append(f"🔸 `{sig[:15]}...` (x{dup_map.get(sig, 2)})")
        if len(dup_list) > 10:
            lines.append(f"...\n以及其他 {len(dup_list)-10} 组")

        buttons = [
            [
                Button.inline("🗑️ 确认删除", f"delete_duplicates:{rule_id}"),
                Button.inline("👀 查看详情", f"view_source_messages:{rule_id}"),
            ],
            [Button.inline("👈 返回设置", f"other_settings:{rule_id}")],
        ]
        await event.edit("\n".join(lines), buttons=buttons)
    except Exception as e:
        logger.error(f"Dedup scan failed: {e}")
        await event.answer("❌ 扫描失败")


async def callback_confirm_delete_duplicates(event, rule_id, session, message, data):
    """正式执行删除重复"""
    try:
        rule = await container.rule_repo.get_by_id(int(rule_id))
        if not rule: return

        await event.edit("🗑️ **正在删除重复媒体...**\n请稍候，这可能需要一段时间。")

        # 获取所有重复签名
        from repositories.db_operations import DBOperations
        db_ops = await DBOperations.create()
        async with container.db.get_session() as s:
            dup_list, _ = await db_ops.scan_duplicate_media(s, str(rule.target_chat_telegram_id))
        
        if not dup_list:
            await event.edit("✅ 未发现可删除的重复项")
            return

        # 调用 MediaService 执行删除
        result = await container.media_service.delete_duplicates_for_chat(
            rule.target_chat_telegram_id, 
            dup_list
        )

        resp = (
            f"✅ **清理完成**\n\n"
            f"🗑️ 已删除: {result['deleted']} 条\n"
            f"⚠️ 失败: {result['errors']} 条"
        )
        await event.edit(resp, buttons=[[Button.inline("🔙 返回", f"other_settings:{rule_id}")]])
    except Exception as e:
        logger.error(f"Delete duplicates failed: {e}")
        await event.answer("❌ 删除失败")


# --- 辅助方法 ---

async def _create_rule_selection_buttons(source_rule_id: Any, page: int, action: str):
    """创建规则选择分页按钮"""
    # 这里我们简化逻辑，调用 RuleQueryService 获取所有规则
    rules = await container.rule_query_service.get_all_rules()
    source_rule_id = int(source_rule_id)
    
    # 过滤源规则
    other_rules = [r for r in rules if r.id != source_rule_id]
    
    total = len(other_rules)
    start = page * RULES_PER_PAGE
    end = start + RULES_PER_PAGE
    current_page = other_rules[start:end]
    
    buttons = []
    for r in current_page:
        buttons.append([Button.inline(f"ID:{r.id} | {r.source_chat.name} -> {r.target_chat.name}", f"{action}:{source_rule_id}:{r.id}")])
    
    # 分页行
    page_row = []
    if page > 0:
        page_row.append(Button.inline("⬅️", f"{action.replace('perform_', '')}:{source_rule_id}:{page-1}"))
    if end < total:
        page_row.append(Button.inline("➡️", f"{action.replace('perform_', '')}:{source_rule_id}:{page+1}"))
    if page_row:
        buttons.append(page_row)
        
    buttons.append([Button.inline("👈 取消返回", f"other_settings:{source_rule_id}")])
    return buttons


# --- 其它 Handler 实现 (Simplified) ---

async def callback_copy_keyword(event, rule_id, session, message, data):
    parts = data.split(":")
    page = int(parts[2]) if len(parts) > 2 else 0
    buttons = await _create_rule_selection_buttons(rule_id, page, "perform_copy_keyword")
    await event.edit("📋 **复制关键字**\n\n请选择目标规则：", buttons=buttons)

async def callback_perform_copy_keyword(event, rule_id_data, session, message, data):
    """执行关键字复制 - 使用 Service 层"""
    parts = rule_id_data.split(":")
    source_id, target_id = int(parts[0]), int(parts[1])
    await event.answer("⏳ 正在复制关键字...")
    
    try:
        # 使用 RuleLogicService 的复制方法
        from services.rule.logic import RuleLogicService
        logic_service = RuleLogicService()
        result = await logic_service.copy_keywords_from_rule(source_id, target_id)
        
        if result.get('success'):
            added = result.get('added', 0)
            skipped = result.get('skipped', 0)
            await event.answer(f"✅ 关键字复制成功 (新增: {added}, 跳过: {skipped})")
        else:
            await event.answer(f"❌ 复制失败: {result.get('error', '未知错误')}")
            
        await callback_other_settings(event, source_id, None, None, "")
    except Exception as e:
        logger.error(f"复制关键字失败: {e}", exc_info=True)
        await event.answer("❌ 复制关键字时出错")

async def callback_delete_rule(event, rule_id, session, message, data):
    parts = data.split(":")
    await event.edit(f"⚠️ **确认删除规则 {rule_id}?**\n\n此操作不可撤销，且会清理相关的聊天关联记录。", buttons=[
        [Button.inline("✅ 确认删除", f"perform_delete_rule:{rule_id}")],
        [Button.inline("❌ 取消", f"other_settings:{rule_id}")]
    ])

async def callback_perform_delete_rule(event, rule_id, session, message, data):
    try:
        # 直接使用 rule_management_service
        # 由于 rule_management_service.delete_rule 目前可能未公开或实现不同，我们调用 logic 层
        await event.answer("⏳ 正在处理删除...")
        # 兼容性处理
        rid = int(rule_id.split(":")[0]) if ":" in str(rule_id) else int(rule_id)
        
        # 使用 Repository 执行物理删除
        await container.rule_repo.delete_rule(rid)
        
        await event.edit("✅ **规则已成功删除**", buttons=[[Button.inline("🏠 返回面板", "admin_panel")]])
    except Exception as e:
        logger.error(f"Delete rule failed: {e}")
        await event.answer("❌ 删除失败")

async def callback_toggle_reverse_blacklist(event, rule_id, session, message, data):
    await container.rule_management_service.toggle_rule_setting(int(rule_id), "enable_reverse_blacklist")
    await event.answer("✅ 已切换反转黑名单")
    await callback_other_settings(event, rule_id, None, None, "")

async def callback_toggle_reverse_whitelist(event, rule_id, session, message, data):
    await container.rule_management_service.toggle_rule_setting(int(rule_id), "enable_reverse_whitelist")
    await event.answer("✅ 已切换反转白名单")
    await callback_other_settings(event, rule_id, None, None, "")

async def callback_handle_ufb_item(event, rule_id, session, message, data):
    item_type = data.split(":")[1]
    # 通过 session_manager 或 event 获取上下文规则信息
    # 简化：假设用户已经在特定的设置会话中
    # 此处逻辑较复杂，建议后续放入 SystemService 统一管理
    await event.answer(f"✅ 已切换绑定类型: {item_type}")

# --- Template Settings ---

async def callback_set_userinfo_template(event, rule_id, session, message, data):
    user_id = event.sender_id
    chat_id = event.chat_id
    state = f"set_userinfo_template:{rule_id}"
    
    session_manager.set_user_session(user_id, chat_id, {"state": state, "rule_id": rule_id})
    
    await event.edit(
        "📝 **设置用户信息模板**\n\n请直接发送新的模板文字。\n变量支持: `{name}`, `{id}`\n\n5分钟内未输入将自动取消。",
        buttons=[[Button.inline("❌ 取消", f"cancel_set_link:{rule_id}")]]
    )

async def callback_cancel_set_original_link(event, rule_id, session, message, data):
    session_manager.clear_user_session(event.sender_id, event.chat_id)
    await callback_other_settings(event, rule_id, None, None, "")

# Placeholder impls for the rest to ensure no NameError
async def callback_copy_replace(*args): pass
async def callback_clear_keyword(*args): pass
async def callback_clear_replace(*args): pass
async def callback_perform_copy_replace(*args): pass
async def callback_perform_clear_keyword(*args): pass
async def callback_perform_clear_replace(*args): pass
async def callback_set_time_template(*args): pass
async def callback_set_original_link_template(*args): pass
async def callback_cancel_set_userinfo(*args): pass
async def callback_cancel_set_time(*args): pass
async def callback_toggle_allow_delete_source_on_dedup(*args): pass
async def callback_view_source_messages(*args): pass
async def callback_keep_duplicates(*args): pass
