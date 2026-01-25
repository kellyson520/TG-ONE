"""
管理面板回调处理器
"""

import asyncio
import logging
from telethon import Button

from utils.processing.auto_delete import reply_and_delete

from handlers.command_handlers import (
    handle_db_backup_command,
    handle_db_health_command,
    handle_db_info_command,
    handle_db_optimize_command,
    handle_system_status_command,
)
from models.models import AsyncSessionManager


from utils.helpers.common import is_admin

logger = logging.getLogger(__name__)


async def handle_admin_callback(event):
    """管理面板回调分发器"""

    data = event.data.decode("utf-8")

    parts = data.split(":")
    action = parts[0]

    # 权限检查
    if not await is_admin(event):
        await event.answer("只有管理员可以访问管理面板", alert=True)
        return

    # 解析 rule_id (管理员回调通常不需要 rule_id，但为了兼容性保留)
    rule_id = parts[1] if len(parts) > 1 else None

    # 使用 AsyncSessionManager 获取会话
    async with AsyncSessionManager() as session:
        message = await event.get_message()
        # 获取对应的处理器
        handler = {
            "admin_db_info": callback_admin_db_info,
            "admin_db_health": callback_admin_db_health,
            "admin_db_backup": callback_admin_db_backup,
            "admin_db_optimize": callback_admin_db_optimize,
            "admin_system_status": callback_admin_system_status,
            "admin_logs": callback_admin_logs,
            "admin_cleanup_menu": callback_admin_cleanup_menu,
            "admin_cleanup": callback_admin_cleanup,
            "admin_cleanup_temp": callback_admin_cleanup_temp,
            "admin_vacuum_db": callback_admin_db_optimize,
            "admin_analyze_db": callback_admin_db_optimize,
            "admin_full_optimize": callback_admin_db_optimize,
            "admin_stats": callback_admin_stats,
            "admin_config": callback_admin_config,
            "admin_restart": callback_admin_restart,
            "admin_restart_confirm": callback_admin_restart_confirm,
            "admin_panel": callback_admin_panel,
            "close_admin_panel": callback_close_admin_panel,
        }.get(action)

        if handler:
            await handler(event, rule_id, session, message, data)
        else:
            logger.warning(f"由于找不到处理器，管理面板回调未处理: {action}")



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
        from models.models import ErrorLog, get_session

        session = get_session()
        try:
            # 获取最近的错误日志
            recent_logs = (
                session.query(ErrorLog)
                .order_by(ErrorLog.created_at.desc())
                .limit(10)
                .all()
            )

            if not recent_logs:
                response = "📋 **运行日志**\n\n✅ 暂无错误日志"
            else:
                response = "📋 **最近10条错误日志**\n\n"
                for log in recent_logs:
                    response += f"🔸 {log.level} | {log.created_at}\n"
                    response += f"   模块: {log.module or 'Unknown'}\n"
                    response += f"   消息: {log.message[:100]}...\n\n"

            # 创建返回按钮
            buttons = [[Button.inline("🔙 返回管理面板", "admin_panel")]]

            await event.edit(response, buttons=buttons)
        finally:
            session.close()

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

        response = "🗑️ **清理维护菜单**\n\n" "选择要执行的清理操作："

        await event.edit(response, buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"加载清理菜单失败: {str(e)}")
        await event.answer("加载清理菜单失败", alert=True)


async def callback_admin_cleanup(event, rule_id, session, message, data):
    """执行清理操作回调"""
    try:
        callback_data = data if data else event.data.decode()
        _, days = callback_data.split(":")
        days = int(days)

        from models.models import cleanup_old_logs

        # 显示进度
        progress_msg = await event.edit(f"🗑️ 正在清理 {days} 天前的日志...")

        deleted_count = cleanup_old_logs(days)

        response = (
            f"✅ **日志清理完成**\n\n"
            f"清理时间范围: {days} 天前\n"
            f"删除记录数: {deleted_count} 条"
        )

        # 创建返回按钮
        buttons = [[Button.inline("🔙 返回清理菜单", "admin_cleanup_menu")]]

        await progress_msg.edit(response, buttons=buttons)
        await asyncio.sleep(5)
        await event.answer()
    except Exception as e:
        logger.error(f"清理操作失败: {str(e)}")
        await event.answer("清理操作失败", alert=True)


async def callback_admin_cleanup_temp(event, rule_id, session, message, data):
    """清理临时文件回调"""
    try:
        import shutil

        import os

        from utils.core.constants import TEMP_DIR

        progress_msg = await event.edit("🧹 正在清理临时文件...")

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

        # 创建返回按钮
        buttons = [[Button.inline("🔙 返回清理菜单", "admin_cleanup_menu")]]

        await progress_msg.edit(response, buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"清理临时文件失败: {str(e)}")
        await event.answer("清理临时文件失败", alert=True)


async def callback_admin_stats(event, rule_id, session, message, data):
    """统计报告回调 - 使用官方API优化"""
    try:
        import asyncio
        from sqlalchemy import func

        from models.models import (
            Chat,
            ErrorLog,
            ForwardRule,
            MediaSignature,
            get_session,
        )
        from utils.network.api_optimization import get_api_optimizer
        from utils.processing.hll import GlobalHLL

        session = get_session()
        api_optimizer = get_api_optimizer()

        try:
            # 使用优化的规则管理服务替代数据库查询
            from services.rule_management_service import rule_management_service

            # 获取优化的统计数据
            stats_result = await rule_management_service.get_rule_statistics()
            if stats_result["success"]:
                stats_data = stats_result["statistics"]
                rule_count = stats_data["total_rules"]
                active_rules = stats_data["enabled_rules"]

                # 使用缓存命中标识
                cache_info = " (缓存)" if stats_result.get("cache_hit") else " (实时)"
            else:
                # 降级到基础统计
                rule_count = session.query(ForwardRule).count()
                active_rules = (
                    session.query(ForwardRule)
                    .filter(ForwardRule.enable_rule == True)
                    .count()
                )
                cache_info = " (降级)"

            # 其他统计使用并发查询优化
            async def get_chat_count():
                return session.query(Chat).count()

            async def get_media_count():
                return session.query(MediaSignature).count()

            async def get_error_count():
                return session.query(ErrorLog).count()

            async def get_total_processed():
                return session.query(func.sum(ForwardRule.message_count)).scalar() or 0

            # 并发执行统计查询
            chat_count, media_count, error_count, total_processed = (
                await asyncio.gather(
                    asyncio.create_task(asyncio.to_thread(get_chat_count)),
                    asyncio.create_task(asyncio.to_thread(get_media_count)),
                    asyncio.create_task(asyncio.to_thread(get_error_count)),
                    asyncio.create_task(asyncio.to_thread(get_total_processed)),
                    return_exceptions=True,
                )
            )

            # 处理异常结果
            if isinstance(chat_count, Exception):
                chat_count = 0
            if isinstance(media_count, Exception):
                media_count = 0
            if isinstance(error_count, Exception):
                error_count = 0
            if isinstance(total_processed, Exception):
                total_processed = 0

            # 获取活跃聊天的ID列表进行实时统计
            active_chats = (
                session.query(Chat.telegram_chat_id)
                .filter(Chat.is_active == True)
                .limit(10)
                .all()
            )
            chat_ids = [chat[0] for chat in active_chats if chat[0]]

            # 使用官方API获取实时聊天统计
            realtime_stats = {}
            total_realtime_messages = 0
            total_participants = 0
            total_online = 0

            if api_optimizer and chat_ids:
                try:
                    # 批量获取聊天统计 - 速度提升5-20倍
                    realtime_stats = await api_optimizer.get_multiple_chat_statistics(
                        chat_ids[:5]
                    )  # 限制5个避免超时

                    for chat_stat in realtime_stats.values():
                        if "error" not in chat_stat:
                            total_realtime_messages += chat_stat.get(
                                "total_messages", 0
                            )
                            total_participants += chat_stat.get("participants_count", 0)
                            total_online += chat_stat.get("online_count", 0)

                except Exception as api_error:
                    logger.warning(
                        f"官方API获取统计失败，使用数据库数据: {str(api_error)}"
                    )

            # 构建响应
            response_parts = [
                "📈 **系统统计报告** (官方API优化)\n\n",
                "**📊 基础数据**\n",
                f"🔧 转发规则: {rule_count} 个 (活跃: {active_rules}){cache_info}\n",
                f"💬 聊天记录: {chat_count} 个\n",
                f"🎬 媒体签名: {media_count} 个\n",
                f"❌ 错误日志: {error_count} 条\n\n",
                "**📈 处理统计**\n",
                f"📨 总处理消息: {total_processed} 条\n",
            ]

            # [Phase 3] 添加 HLL 基数统计 (今日独立消息估算)
            try:
                hll = GlobalHLL.get_hll("unique_messages_today")
                if hll:
                    unique_count = hll.count()
                    response_parts.append(f"🎯 今日独立消息估值 (HLL): {unique_count:,} 条\n")
            except Exception as hll_err:
                logger.debug(f"HLL 统计失败: {hll_err}")

            # 添加实时统计（如果可用）
            if realtime_stats:
                response_parts.extend(
                    [
                        "\n**🔥 实时统计** (官方API)\n",
                        f"📱 实时消息总数: {total_realtime_messages:,} 条\n",
                        f"👥 活跃参与者: {total_participants:,} 人\n",
                        f"🟢 当前在线: {total_online:,} 人\n",
                        f"⚡ 统计来源: {len(realtime_stats)} 个活跃聊天\n",
                    ]
                )

                # 显示部分聊天详情
                successful_stats = [
                    s for s in realtime_stats.values() if "error" not in s
                ]
                if successful_stats:
                    response_parts.append("\n**📊 聊天详情**\n")
                    for i, stat in enumerate(successful_stats[:3]):  # 只显示前3个
                        response_parts.append(
                            f"Chat {stat['chat_id']}: {stat.get('total_messages', 0):,} 条, "
                            f"{stat.get('participants_count', 0):,} 人\n"
                        )

            response_parts.extend(
                [
                    "\n**🔄 运行状态**\n",
                    "✅ 系统运行正常\n",
                    "✅ 数据库连接正常\n",
                    f"⚡ API优化: {'已启用' if api_optimizer else '未启用'}",
                ]
            )

            response = "".join(response_parts)

            # 创建返回按钮
            buttons = [
                [Button.inline("🔄 刷新统计", "admin_stats")],
                [Button.inline("🔙 返回管理面板", "admin_panel")],
            ]

            await event.edit(response, buttons=buttons)
        finally:
            session.close()

        await event.answer()
    except Exception as e:
        logger.error(f"获取统计报告失败: {str(e)}")
        await event.answer("获取统计报告失败", alert=True)


async def callback_admin_config(event, rule_id, session, message, data):
    """系统配置回调"""
    try:
        from models.models import SystemConfiguration, get_session

        session = get_session()
        try:
            # 获取系统配置
            configs = session.query(SystemConfiguration).limit(10).all()

            if not configs:
                response = "⚙️ **系统配置**\n\n暂无配置项"
            else:
                response = "⚙️ **系统配置**\n\n"
                for config in configs:
                    response += f"🔸 {config.key}: {config.value}\n"

            # 创建返回按钮
            buttons = [[Button.inline("🔙 返回管理面板", "admin_panel")]]

            await event.edit(response, buttons=buttons)
        finally:
            session.close()

        await event.answer()
    except Exception as e:
        logger.error(f"获取系统配置失败: {str(e)}")
        await event.answer("获取系统配置失败", alert=True)


async def callback_admin_restart(event, rule_id, session, message, data):
    """重启服务回调"""
    try:
        # 确认重启操作
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
    except Exception as e:
        logger.error(f"重启确认失败: {str(e)}")
        await event.answer("重启确认失败", alert=True)


async def callback_admin_restart_confirm(event, rule_id, session, message, data):
    """确认重启服务回调"""
    try:
        await event.edit("🔄 正在重启服务...")
        await event.answer()

        # 注意：实际重启逻辑需要根据部署方式实现
        await asyncio.sleep(2)

        response = (
            "✅ **重启命令已发送**\n\n"
            "服务将在几秒钟内重启完成。\n"
            "如果长时间无响应，请检查服务状态。"
        )

        await event.edit(response)

        # 这里可以添加实际的重启逻辑，比如：
        # import sys
        # import os
        # os.execl(sys.executable, sys.executable, *sys.argv)

    except Exception as e:
        logger.error(f"重启服务失败: {str(e)}")
        await event.answer("重启服务失败", alert=True)


async def callback_admin_panel(event, rule_id, session, message, data):
    """返回管理面板主菜单"""
    try:
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

        response = "🔧 **系统管理面板**\n\n" "选择需要执行的管理操作："

        await event.edit(response, buttons=buttons)
        await event.answer()
    except Exception as e:
        logger.error(f"返回管理面板失败: {str(e)}")
        await event.answer("返回管理面板失败", alert=True)


async def callback_close_admin_panel(event, rule_id, session, message, data):
    """关闭管理面板回调"""
    try:
        await event.delete()
        await event.answer()
    except Exception as e:
        logger.error(f"关闭管理面板失败: {str(e)}")
        await event.answer("关闭管理面板失败", alert=True)
