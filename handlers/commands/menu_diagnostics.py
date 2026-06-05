"""
菜单系统性能监控和诊断工具

提供性能统计查看、未匹配actions追踪等功能
"""
from telethon import events
from core.helpers.common import is_admin
from handlers.button.strategies.registry import MenuHandlerRegistry
import logging

logger = logging.getLogger(__name__)


async def menu_stats_command(event):
    """查看菜单系统性能统计"""
    if not await is_admin(event):
        await event.reply("⚠️ 此命令仅限管理员使用")
        return
    
    try:
        # 获取性能统计
        perf_stats = MenuHandlerRegistry.get_performance_stats(top_n=15)
        unmatched = MenuHandlerRegistry.get_unmatched_actions()
        
        # 构建报告
        lines = ["📊 **菜单系统性能报告**\n"]
        
        # Top actions
        if perf_stats:
            lines.append("**🔥 最常用的Actions (Top 15):**")
            for action, stats in perf_stats.items():
                avg_ms = stats['avg_time'] * 1000
                max_ms = stats['max_time'] * 1000
                lines.append(
                    f"• `{action}`: {stats['count']}次 "
                    f"(avg: {avg_ms:.1f}ms, max: {max_ms:.1f}ms)"
                )
            lines.append("")
        
        # Unmatched actions
        if unmatched:
            lines.append("**⚠️ 未匹配的Actions:**")
            sorted_unmatched = sorted(unmatched.items(), key=lambda x: x[1], reverse=True)
            for action, count in sorted_unmatched[:10]:
                emoji = "🚨" if count >= 10 else "⚠️"
                lines.append(f"{emoji} `{action}`: {count}次未匹配")
            lines.append("")
        else:
            lines.append("✅ **没有未匹配的actions**\n")
        
        # Registered handlers
        handlers = MenuHandlerRegistry.get_registered_handlers()
        lines.append(f"**📦 已注册的策略 ({len(handlers)}):**")
        lines.append(", ".join(f"`{h}`" for h in handlers))
        
        report = "\n".join(lines)
        await event.reply(report)
        
    except Exception as e:
        logger.error(f"生成菜单统计失败: {e}", exc_info=True)
        await event.reply(f"❌ 生成统计失败: {e}")


async def reset_menu_stats_command(event):
    """重置菜单系统统计"""
    if not await is_admin(event):
        await event.reply("⚠️ 此命令仅限管理员使用")
        return
    
    try:
        MenuHandlerRegistry.reset_stats()
        await event.reply("✅ 菜单系统统计已重置")
    except Exception as e:
        logger.error(f"重置菜单统计失败: {e}", exc_info=True)
        await event.reply(f"❌ 重置失败: {e}")


# 注册命令（需要在 handlers/bot_handler.py 中添加）
MENU_DIAGNOSTIC_COMMANDS = {
    "menu_stats": menu_stats_command,
    "reset_menu_stats": reset_menu_stats_command,
}
