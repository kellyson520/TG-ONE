"""
管理面板回调处理器
"""

import asyncio
import logging
from telethon import Button

from core.container import container
from handlers.command_handlers import (
    handle_db_backup_command,
    handle_db_health_command,
    handle_db_info_command,
    handle_db_optimize_command,
    handle_system_status_command,
)

logger = logging.getLogger(__name__)


async def handle_admin_callback(event, **kwargs):
    """管理面板回调分发器 - Refactored to use Strategy Registry"""
    try:
        data = event.data.decode("utf-8")
        parts = data.split(":")
        action = parts[0]
        
        from handlers.button.strategies import MenuHandlerRegistry

        if await MenuHandlerRegistry.dispatch(event, action, data=data, **kwargs):
            return

        logger.warning(f"由于找不到处理器，管理面板回调未处理: {action}")
        await event.answer("⚠️ 未知指令", alert=True)

    except Exception as e:
        logger.error(f"处理管理回调失败: {e}", exc_info=True)
        await event.answer("⚠️ 系统繁忙", alert=True)


async def callback_admin_db_info(event, rule_id, session, message, data):
    """数据库信息回调"""
    try:
        await handle_db_info_command(event)
        await event.answer()
    except Exception as e:
        logger.error(f"获取数据库信息失败: {str(e)}")
        await event.answer("获取数据库信息失败", alert=True)


async def callback_admin_db_health(event, rule_id, session, message, data):
    """数据库健康检查回调"""
    try:
        await handle_db_health_command(event)
        await event.answer()
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        await event.answer("健康检查失败", alert=True)


async def callback_admin_db_backup(event, rule_id, session, message, data):
    """数据库备份回调"""
    try:
        await handle_db_backup_command(event)
        await event.answer()
    except Exception as e:
        logger.error(f"数据库备份失败: {str(e)}")
        await event.answer("数据库备份失败", alert=True)


async def callback_admin_db_optimize(event, rule_id, session, message, data):
    """数据库优化回调"""
    try:
        await handle_db_optimize_command(event)
        await event.answer()
    except Exception as e:
        logger.error(f"数据库优化失败: {str(e)}")
        await event.answer("数据库优化失败", alert=True)


async def callback_admin_system_status(event, rule_id, session, message, data):
    """系统状态回调"""
    try:
        await handle_system_status_command(event)
        await event.answer()
    except Exception as e:
        logger.error(f"获取系统状态失败: {str(e)}")
        await event.answer("获取系统状态失败", alert=True)


async def callback_admin_logs(event, rule_id, session, message, data):
    """运行日志回调"""
    try:
        # 使用 SystemService 获取日志
        recent_logs = await container.system_service.get_error_logs(limit=10)

        if not recent_logs:
            response = "📋 **运行日志**\n\n✅ 暂无错误日志"
        else:
            response = "📋 **最近10条错误日志**\n\n"
            for log in recent_logs:
                response += f"🔸 {log.level} | {log.created_at}\n"
                response += f"   模块: {log.module or 'Unknown'}\n"
                response += f"   消息: {log.message[:100]}...\n\n"

        buttons = [[Button.inline("🔙 返回管理面板", "admin_panel")]]
        await event.edit(response, buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"获取运行日志失败: {str(e)}")
        await event.answer("获取运行日志失败", alert=True)


async def callback_admin_cleanup_menu(event, rule_id, session, message, data):
    """清理维护菜单回调"""
    try:
        buttons = [
            [
                Button.inline("🗑️ 清理日志(7天)", "admin_cleanup:7"),
                Button.inline("🗑️ 清理日志(30天)", "admin_cleanup:30"),
            ],
            [
                Button.inline("🧹 清理临时文件", "admin_cleanup_temp"),
                Button.inline("💾 释放磁盘空间", "admin_vacuum_db"),
            ],
            [
                Button.inline("📊 数据库分析", "admin_analyze_db"),
                Button.inline("🔄 完整优化", "admin_full_optimize"),
            ],
            [Button.inline("🔙 返回管理面板", "admin_panel")],
        ]

        response = "🗑️ **清理维护菜单**\n\n选择要执行的清理操作："
        await event.edit(response, buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"加载清理菜单失败: {str(e)}")
        await event.answer("加载清理菜单失败", alert=True)


async def callback_admin_cleanup(event, rule_id, session, message, data):
    """执行清理操作回调 - 使用 Service 层"""
    try:
        parts = data.split(":")
        days = int(parts[1]) if len(parts) > 1 else 30

        # 显示进度
        await event.edit(f"🗑️ 正在清理 {days} 天前的日志...")
        
        # 使用 SystemService 清理日志
        from services.system_service import system_service
        result = await system_service.cleanup_old_logs(days)
        
        if result.get('success'):
            deleted_count = result.get('deleted_count', 0)
            response = (
                f"✅ **日志清理完成**\n\n"
                f"清理时间范围: {days} 天前\n"
                f"删除记录数: {deleted_count} 条"
            )
        else:
            response = (
                f"❌ **日志清理失败**\n\n"
                f"错误信息: {result.get('error', '未知错误')}"
            )

        buttons = [[Button.inline("🔙 返回清理菜单", "admin_cleanup_menu")]]
        await event.edit(response, buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"清理操作失败: {str(e)}")
        await event.answer("清理操作失败", alert=True)


async def callback_admin_cleanup_temp(event, rule_id, session, message, data):
    """清理临时文件回调"""
    try:
        await event.edit("🧹 正在清理临时文件...")
        
        # 实际清理逻辑已经在 SystemService 中有类似实现，但这里直接调用的系统命令或特定逻辑
        # 我们暂时保留原逻辑，但确保它干净
        import shutil
        import os
        from core.constants import TEMP_DIR

        deleted_count = 0
        deleted_size = 0

        if os.path.exists(TEMP_DIR):
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        deleted_size += file_size
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        deleted_count += 1
                except Exception:
                    continue

        response = (
            f"✅ **临时文件清理完成**\n\n"
            f"删除文件数: {deleted_count} 个\n"
            f"释放空间: {deleted_size/1024/1024:.2f} MB"
        )

        buttons = [[Button.inline("🔙 返回清理菜单", "admin_cleanup_menu")]]
        await event.edit(response, buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"清理临时文件失败: {str(e)}")
        await event.answer("清理临时文件失败", alert=True)


async def callback_admin_stats(event, rule_id, session, message, data):
    """统计报告回调 - 重构为使用 SystemService"""
    try:
        await event.edit("📈 正在采集统计数据...")
        
        stats = await container.system_service.get_advanced_stats()
        base = stats["base"]
        
        response_parts = [
            "📈 **系统统计报告**\n\n",
            "**📊 基础数据**\n",
            f"🔧 转发规则: {base['total_rules']} 个 (活跃: {base['active_rules']})\n",
            f"💬 聊天记录: {base['chat_count']} 个\n",
            f"🎬 媒体签名: {base['media_count']} 个\n",
            f"❌ 错误日志: {base['error_count']} 条\n\n",
            "**📈 处理统计**\n",
            f"📨 总处理消息: {base['total_processed']} 条\n",
        ]

        if stats.get("unique_today"):
            response_parts.append(f"🎯 今日独立消息估值 (HLL): {stats['unique_today']:,} 条\n")

        realtime = stats.get("realtime", {})
        if realtime:
            total_msgs = sum(s.get("total_messages", 0) for s in realtime.values() if "error" not in s)
            total_users = sum(s.get("participants_count", 0) for s in realtime.values() if "error" not in s)
            response_parts.extend([
                "\n**🔥 实时统计** (官方API)\n",
                f"📱 采样消息总数: {total_msgs:,} 条\n",
                f"👥 采样参与者: {total_users:,} 人\n",
                f"⚡ 采样来源: {len(realtime)} 个活跃聊天\n",
            ])

        response_parts.extend([
            "\n**🔄 运行状态**\n",
            "✅ 系统运行正常\n",
            f"⚡ API优化: {'已开启' if stats['api_enabled'] else '未开启'}",
        ])

        buttons = [
            [Button.inline("🔄 刷新统计", "admin_stats")],
            [Button.inline("🔙 返回管理面板", "admin_panel")],
        ]

        await event.edit("".join(response_parts), buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"获取统计报告失败: {str(e)}", exc_info=True)
        await event.answer("获取统计报告失败", alert=True)


async def callback_admin_config(event, rule_id, session, message, data):
    """系统配置回调"""
    try:
        configs = await container.system_service.get_system_configurations(limit=10)

        if not configs:
            response = "⚙️ **系统配置**\n\n暂无配置项"
        else:
            response = "⚙️ **系统配置**\n\n"
            for config in configs:
                response += f"🔸 {config.key}: {config.value}\n"

        buttons = [[Button.inline("🔙 返回管理面板", "admin_panel")]]
        await event.edit(response, buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"获取系统配置失败: {str(e)}")
        await event.answer("获取系统配置失败", alert=True)


async def callback_admin_restart(event, rule_id, session, message, data):
    """重启服务回调"""
    buttons = [
        [
            Button.inline("✅ 确认重启", "admin_restart_confirm"),
            Button.inline("❌ 取消", "admin_panel"),
        ]
    ]

    response = (
        "🔄 **重启服务确认**\n\n"
        "⚠️ 确定要重启服务吗？\n"
        "重启过程中服务将暂时不可用。"
    )

    await event.edit(response, buttons=buttons)
    await event.answer()


async def callback_admin_restart_confirm(event, rule_id, session, message, data):
    """确认重启服务回调"""
    try:
        await event.edit("🔄 正在触发系统重启...")
        await event.answer()
        
        # 触发重启
        from services.system_service import guard_service
        guard_service.trigger_restart()
        
    except Exception as e:
        logger.error(f"重启服务失败: {str(e)}")
        await event.answer("重启服务失败", alert=True)


async def callback_admin_panel(event, rule_id, session, message, data):
    """返回管理面板主菜单"""
    buttons = [
        [
            Button.inline("📊 数据库信息", "admin_db_info"),
            Button.inline("💚 健康检查", "admin_db_health"),
        ],
        [
            Button.inline("💾 备份数据库", "admin_db_backup"),
            Button.inline("🔧 优化数据库", "admin_db_optimize"),
        ],
        [
            Button.inline("🖥️ 系统状态", "admin_system_status"),
            Button.inline("📋 运行日志", "admin_logs"),
        ],
        [
            Button.inline("🗑️ 清理维护", "admin_cleanup_menu"),
            Button.inline("📈 统计报告", "admin_stats"),
        ],
        [
            Button.inline("⚙️ 系统配置", "admin_config"),
            Button.inline("🔄 重启服务", "admin_restart"),
        ],
        [Button.inline("❌ 关闭面板", "close_admin_panel")],
    ]

    response = "🔧 **系统管理面板**\n\n选择需要执行的管理操作："
    await event.edit(response, buttons=buttons)
    await event.answer()


async def callback_close_admin_panel(event, rule_id, session, message, data):
    """关闭管理面板回调"""
    try:
        await event.delete()
        await event.answer()
    except Exception:
        pass
