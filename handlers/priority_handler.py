from telethon import events
import logging
from typing import Optional
from services.rule.facade import rule_management_service
from core.container import container
from core.helpers.common import is_admin_or_owner
from core.config import settings
from services.queue_service import MessageQueueService

logger = logging.getLogger(__name__)

async def set_priority_handler(event):
    """
    处理 /set_priority (alias /vip, /p) 指令
    
    Usage:
    - Group: /vip <priority> (设置当前群组规则优先级)
    - Private: /vip <rule_id> <priority> (设置指定规则优先级)
    """
    if not await is_admin_or_owner(event.sender_id):
        # Fail silently or generic denied
        return

    args = event.text.split()
    cmd = args[0].lower()
    
    # [Context Awareness]
    is_private = event.is_private
    chat_id = event.chat_id
    
    usage_msg = (
        "**指令用法**:\n"
        "• 群组内: `/vip <priority>`\n"
        "• 私聊中: `/vip <rule_id> <priority>`\n"
        "`/vip <priority>` (设置当前规则优先级)\n"
        "`/vip 100` (🚑 CRITICAL / Emergency)\n"
        "`/vip 50` (🏎️ FAST / VIP)\n"
        "`/vip 10` (🚗 STANDARD / Normal)\n"
        "`/vip 0` (🚗 STANDARD / Bulk)"
    )

    rule_id: Optional[int] = None
    priority: Optional[int] = None

    try:
        if is_private:
            # Expect: /vip <rule_id> <priority>
            if len(args) < 3:
                await event.reply(f"❌ 参数不足。\n{usage_msg}")
                return
            rule_id = int(args[1])
            priority = int(args[2])
        else:
            # Expect: /vip <priority>
            if len(args) < 2:
                await event.reply(f"❌ 参数不足。\n{usage_msg}")
                return
            
            priority = int(args[1])
            # Find rule for current chat
            # We need to query RuleRepo to find rule where source_chat_id matches current chat
            # This is complex because mapping table.
            # Simplified: Let's assume user wants to boost *any* rule related to this source chat.
            # But wait, RuleService updates by Rule ID.
            # We need a helper to find Rule ID by Chat ID.
            
            # Helper: find rules by source chat
            # Since RuleRepo doesn't expose strict 'get_rule_by_source' easily in facade,
            # we might better suggest using Rule ID even in group, or query DB.
            # Let's try advanced lookup.
            
            # Actually, let's use the new `get_priority_map` logic in reverse or query DB directly via Repo
            stmt = (
                f"SELECT id FROM forward_rules "
                f"JOIN chats ON forward_rules.source_chat_id = chats.id "
                f"WHERE chats.telegram_chat_id = '{chat_id}' AND forward_rules.enable_rule = 1 "
                f"LIMIT 1"
            )
            # This is raw SQL, risky. Let's use Repo.
            # Ideally `rule_repo.get_rules_by_source(chat_id)`
            # For now, let's look for Rule corresponding to this chat.
            
            # 临时方案：遍历所有规则（不推荐），或者只需用户提供 Rule ID。
            # 为了 UX，我们尝试自动查找。
            rules_result = await rule_management_service.get_rule_list(page_size=1000) # In memory filter
            # Logic: Input chat_id is Telegram ID.
            target_rule = None
            if rules_result.get('rules'):
                for r in rules_result['rules']:
                    if str(r['source_chat'].get('telegram_chat_id')) == str(chat_id):
                        target_rule = r
                        break
            
            if not target_rule:
                await event.reply("❌ 当前群组未配置任何转发规则。请先配置规则。")
                return
            
            rule_id = target_rule['id']

        # Execute Update
        result = await rule_management_service.update_rule(rule_id, priority=priority)
        
        if result.get('success'):
            from core.helpers.priority_utils import get_priority_description
            p_desc = get_priority_description(priority)
            await event.reply(
                f"✅ **优先级已更新**\n"
                f"• 规则 ID: `{rule_id}`\n"
                f"• 新优先级: `{p_desc} ({priority})`\n"
                f"• 状态: 已生效 (Cached)"
            )
        else:
            await event.reply(f"❌ 更新失败: {result.get('error')}")

    except ValueError:
        await event.reply("❌ 参数错误：ID 和 优先级必须为整数。")
    except Exception as e:
        logger.error(f"Set priority failed: {e}")
        await event.reply("❌ 系统内部错误")


async def queue_status_handler(event):
    """
    处理 /queue_status 指令
    显示 QoS 4.0 泳道状态与拥塞情况
    """
    if not await is_admin_or_owner(event.sender_id):
        return

    qs = container.queue_service
    if not hasattr(qs, 'lanes'):
        await event.reply("⚠️ QueueService 未升级至 QoS 4.0。")
        return

    # 1. 数据库任务状态 (Database Layer)
    db_stats = await container.task_repo.get_queue_status()
    msg = "**🚦 队列状态 (QoS 4.0)**\n\n"
    msg += "**任务积压 (Database):**\n"
    msg += f"• ⏳ 等待中: `{db_stats['active_queues']}`\n"
    msg += f"• ⚡ 正在运行: `{db_stats['running_tasks']}`\n"
    msg += f"• 📊 平均延迟: `{db_stats['avg_delay']}`\n"
    msg += f"• ❌ 失败率: `{db_stats['error_rate']}`\n\n"

    # 2. 内存泳道深度 (Memory Layer)
    msg += "**泳道深度 (Lane Depths):**\n"
    
    total_mem = 0
    for name, q in qs.lanes.items():
        size = q.qsize()
        total_mem += size
        icon = "🟢" if size < 10 else "🟡" if size < 100 else "🔴"
        msg += f"{icon} `{name.upper()}`: **{size}**\n"
    
    msg += f"\n**内存总积压:** `{total_mem}`\n"
    
    # 3. 拥塞 Top 5
    if qs.pending_counts:
        msg += "\n**拥塞群组 Top 5:**\n"
        # Sort by count desc
        top_congestion = sorted(qs.pending_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        for chat_id, count in top_congestion:
            # Try to get name
            from core.helpers.id_utils import get_display_name_async
            name = await get_display_name_async(chat_id)
            
            penalty = count * qs.CONGESTION_PENALTY_FACTOR
            msg += f"• {name}: `{count}` (负载分: -{penalty:.1f})\n"
    else:
        msg += "\n✅ 无拥塞群组。\n"

    await event.reply(msg)
