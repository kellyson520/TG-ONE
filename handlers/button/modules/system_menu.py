"""
系统管理菜单模块
处理数据库备份、系统概览、缓存清理等
"""
import os
import logging
from datetime import datetime
from telethon import Button
from ..base import BaseMenu
from core.config import settings

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

class SystemMenu(BaseMenu):
    """系统管理菜单"""

    async def show_system_settings(self, event):
        """显示系统设置菜单"""
        buttons = [
            [Button.inline("💾 数据库备份", "new_menu:db_backup")],
            [Button.inline("📦 数据库归档", "new_menu:db_archive_center")],
            [Button.inline("📊 系统概况", "new_menu:system_overview")],
            [Button.inline("🗑️ 缓存清理", "new_menu:cache_cleanup")],
            [Button.inline("👈 返回上一级", "new_menu:system_hub")],
        ]
        await self._render_page(
            event,
            title="⚙️ **系统设置**",
            body_lines=["选择需要执行的系统管理操作："],
            buttons=buttons,
            breadcrumb="🏠 主菜单 > ⚙️ 系统设置",
        )

    async def show_db_backup_menu(self, event):
        """显示数据库备份菜单"""
        buttons = [
            [Button.inline("✅ 备份当前数据", "new_menu:backup_current")],
            [Button.inline("📂 查看历史备份", "new_menu:view_backups")],
            [Button.inline("👈 返回上一级", "new_menu:system_hub")],
        ]
        await self._render_page(
            event,
            title="💾 **数据库备份**",
            body_lines=["选择备份相关操作："],
            buttons=buttons,
            breadcrumb="🏠 主菜单 > ⚙️ 系统设置 > 💾 数据库备份",
        )

    async def confirm_backup(self, event):
        """确认备份数据"""
        buttons = [
            [Button.inline("✅ 是", "new_menu:do_backup")],
            [Button.inline("❌ 否", "new_menu:db_backup")],
            [Button.inline("👈 返回上一级", "new_menu:db_backup")],
        ]
        text = "❓ **是否备份当前数据？**\n\n此操作将创建当前数据库的完整备份。"
        await self._render_from_text(event, text, buttons)

    async def do_backup(self, event):
        """执行数据库备份"""
        try:
            await self._render_from_text(event, "🔄 正在备份数据库...", buttons=None)
            from services.system_service import system_service
            result = await system_service.backup_database()

            if result.get("success"):
                text = (
                    "✅ **数据库备份成功**\n\n"
                    f"数据大小：{result.get('size_mb', 0):.2f} MB\n"
                    f"备份位置：{result.get('path')}"
                )
            else:
                text = (
                    "❌ **数据库备份失败**\n\n"
                    f"错误信息：{result.get('error', '未知错误')}"
                )
            buttons = [[Button.inline("👈 返回上一级", "new_menu:db_backup")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"备份数据库失败: {str(e)}")
            buttons = [[Button.inline("👈 返回上一级", "new_menu:db_backup")]]
            await self._render_from_text(event, "❌ **数据库备份失败**\n\n请检查日志", buttons)

    async def show_backup_history(self, event, page=0):
        """显示历史备份"""
        try:
            backup_dirs = [str(settings.BACKUP_DIR), str(settings.DB_DIR / "backup")]
            backup_files = []
            for backup_dir in backup_dirs:
                if os.path.exists(backup_dir):
                    for file in os.listdir(backup_dir):
                        if file.endswith(".db"):
                            filepath = os.path.join(backup_dir, file)
                            try:
                                stat = os.stat(filepath)
                                backup_files.append({
                                    "name": file,
                                    "path": filepath,
                                    "size": stat.st_size,
                                    "time": datetime.fromtimestamp(stat.st_mtime),
                                })
                            except Exception as e:
                                logger.debug(f"[SystemMenu] Failed to stat backup file {filepath}: {e}")

            if not backup_files:
                text = "📂 **历史备份**\n\n暂无备份文件"
                buttons = [[Button.inline("👈 返回上一级", "new_menu:db_backup")]]
                await self._render_from_text(event, text, buttons)
                return

            backup_files.sort(key=lambda x: x["time"].timestamp(), reverse=True)
            per_page = 5
            start = page * per_page
            end = start + per_page
            page_files = backup_files[start:end]

            text = "📂 **历史备份**\n\n"
            buttons = []
            for i, backup in enumerate(page_files):
                size_mb = backup["size"] / (1024 * 1024)
                time_str = backup["time"].strftime("%Y-%m-%d %H:%M:%S")
                button_text = f"{backup['name']} ({size_mb:.1f}MB, {time_str})"
                buttons.append([Button.inline(button_text, f"new_menu:restore_backup:{i+start}")])

            nav_buttons = []
            if page > 0:
                nav_buttons.append(Button.inline("⬅️ 上一页", f"new_menu:backup_page:{page-1}"))
            if end < len(backup_files):
                nav_buttons.append(Button.inline("下一页 ➡️", f"new_menu:backup_page:{page+1}"))
            if nav_buttons:
                buttons.append(nav_buttons)

            buttons.append([Button.inline("👈 返回上一级", "new_menu:db_backup")])
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"显示备份历史失败: {str(e)}")

    async def confirm_restore_backup(self, event, backup_index):
        """确认恢复备份"""
        buttons = [
            [Button.inline("✅ 是", f"new_menu:do_restore:{backup_index}")],
            [Button.inline("❌ 否", "new_menu:view_backups")],
            [Button.inline("👈 返回上一级", "new_menu:view_backups")],
        ]
        text = "❓ **是否恢复历史备份？**\n\n⚠️ 此操作将覆盖当前数据库，请谨慎操作！"
        await self._render_from_text(event, text, buttons)

    async def do_restore(self, event, backup_index):
        """执行数据库恢复"""
        try:
            await self._render_from_text(event, "🔄 正在恢复数据库...", buttons=None)
            
            # 重新获取备份列表
            backup_dirs = [str(settings.BACKUP_DIR), str(settings.DB_DIR / "backup")]
            backup_files = []
            for backup_dir in backup_dirs:
                if os.path.exists(backup_dir):
                    for file in os.listdir(backup_dir):
                        if file.endswith(".db"):
                            filepath = os.path.join(backup_dir, file)
                            stat = os.stat(filepath)
                            backup_files.append({
                                "path": filepath,
                                "time": datetime.fromtimestamp(stat.st_mtime),
                            })
            backup_files.sort(key=lambda x: x["time"].timestamp(), reverse=True)
            
            idx = int(backup_index)
            if 0 <= idx < len(backup_files):
                backup_path = backup_files[idx]["path"]
                from services.system_service import system_service
                result = await system_service.restore_database(backup_path)
                
                if result.get("success"):
                    text = "✅ **数据库恢复成功**\n\n系统可能需要重启以应用所有更改。"
                else:
                    text = f"❌ **数据库恢复失败**\n\n错误：{result.get('error')}"
            else:
                text = "❌ **恢复失败**：找不到备份文件"
            
            buttons = [[Button.inline("👈 返回上一级", "new_menu:view_backups")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"恢复数据库失败: {str(e)}")
            await event.answer(f"操作失败: {e}", alert=True)

    async def show_system_overview(self, event):
        """显示系统概况"""
        try:
            if PSUTIL_AVAILABLE:
                uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
                uptime_str = str(uptime).split(".")[0]
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                disk = psutil.disk_usage("/")
                disk_percent = (disk.used / disk.total) * 100
            else:
                uptime_str, memory_percent, disk_percent = "未知", 0, 0

            from pathlib import Path
            db_size_str = "未知"
            try:
                db_path = (settings.DB_DIR / "forward.db").resolve()
                if db_path.exists():
                    db_size_str = f"{os.path.getsize(str(db_path)) / (1024 * 1024):.2f} MB"
            except Exception as e:
                logger.debug(f"[SystemMenu] Failed to get db size: {e}")

            log_size_str, error_count, warning_count, info_count = "未知", 0, 0, 0
            try:
                log_dir = settings.LOG_DIR
                total_log_size = 0
                if os.path.isdir(log_dir):
                    for name in os.listdir(log_dir):
                        if name.lower().endswith(".log"):
                            file_path = os.path.join(log_dir, name)
                            try:
                                total_log_size += os.path.getsize(file_path)
                                with open(file_path, "r", encoding="utf-8", errors="ignore") as lf:
                                    for line in lf:
                                        if " - ERROR - " in line or " ERROR " in line or line.startswith("ERROR"): error_count += 1
                                        elif " - WARNING - " in line or " WARNING " in line or line.startswith("WARNING"): warning_count += 1
                                        elif " - INFO - " in line or " INFO " in line or line.startswith("INFO"): info_count += 1
                            except Exception as e:
                                logger.debug(
                                    "SystemMenu failed to read log file: path=%s error=%s",
                                    file_path,
                                    e,
                                )
                                continue
                log_size_str = f"{total_log_size / (1024 * 1024):.2f} MB"
            except Exception as e:
                logger.debug(f"[SystemMenu] Failed to calculate log stats: {e}")

            buttons = [
                [Button.inline("🔄 刷新", "new_menu:system_overview")],
                [Button.inline("👈 返回上一级", "new_menu:system_settings")],
            ]
            await self._render_page(
                event,
                title="📊 **系统概况**",
                body_lines=[
                    f"运行时间：{uptime_str}", "服务器状态：正常运行",
                    f"内存使用：{memory_percent:.1f}%", f"磁盘使用：{disk_percent:.1f}%",
                    f"数据大小：{db_size_str}", f"日志大小：{log_size_str}",
                    f"ERROR：{error_count}", f"WARNING：{warning_count}", f"INFO：{info_count}",
                ],
                buttons=buttons,
                breadcrumb="🏠 主菜单 > ⚙️ 系统设置 > 📈 系统概况",
            )
        except Exception as e:
            logger.error(f"获取系统概况失败: {str(e)}")
            buttons = [[Button.inline("👈 返回上一级", "new_menu:system_settings")]]
            await self._render_from_text(event, f"❌ **获取系统概况失败**\n\n{e}", buttons)

    async def confirm_cache_cleanup(self, event):
        """确认缓存清理"""
        buttons = [
            [Button.inline("✅ 是", "new_menu:do_cleanup")],
            [Button.inline("❌ 否", "new_menu:system_settings")],
            [Button.inline("👈 返回上一级", "new_menu:system_settings")],
        ]
        text = "❓ **是否进行缓存清理？**\n\n此操作将清理临时文件和缓存数据。"
        await self._render_from_text(event, text, buttons)

    async def do_cache_cleanup(self, event):
        """执行缓存清理"""
        try:
            cleaned_files = 0
            cleaned_size = 0
            temp_dirs = [str(settings.TEMP_DIR)]
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            try:
                                fp = os.path.join(root, file)
                                s = os.path.getsize(fp)
                                os.remove(fp)
                                cleaned_files += 1
                                cleaned_size += s
                            except Exception as e:
                                logger.debug(f"[SystemMenu] Cleanup temp error: {e}")
                                continue
            try:
                log_dir = settings.LOG_DIR
                if os.path.exists(log_dir):
                    for f in os.listdir(log_dir):
                        if f.endswith(".log.old") or f.endswith(".log.1"):
                            fp = os.path.join(log_dir, f)
                            s = os.path.getsize(fp)
                            os.remove(fp)
                            cleaned_files += 1
                            cleaned_size += s
            except Exception as e:
                logger.debug(f"[SystemMenu] Log cleanup error: {e}")

            text = f"✅ **清理报告**\n\n清理了{cleaned_files}个文件\n共{cleaned_size/1024:.2f}KB"
            buttons = [[Button.inline("👈 返回上一级", "new_menu:system_settings")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"缓存清理失败: {str(e)}")
            buttons = [[Button.inline("👈 返回上一级", "new_menu:system_settings")]]
            await self._render_from_text(event, f"❌ **缓存清理失败**\n\n{e}", buttons)

    async def show_system_status(self, event):
        """显示系统状态 - 使用 Service 层"""
        try:
            from services.system_service import system_service
            db = await system_service.get_db_health()
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            text = (
                "🩺 **系统状态监控**\n\n"
                f"🗄️ 数据库: {'✅ 正常' if db.get('connected') else '❌ 异常'}\n"
                f"💻 CPU 使用率: {cpu:.1f}%\n"
                f"🧠 内存 使用率: {mem:.1f}%\n"
                f"🕒 系统运行正常"
            )
            buttons = [[Button.inline("🔄 刷新", "new_menu:system_status")], [Button.inline("👈 返回上一级", "new_menu:system_hub")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"显示系统状态失败: {e}")

    async def show_log_viewer(self, event):
        """查看最近日志"""
        try:
            import os
            log_dir = settings.LOG_DIR
            log_file = os.path.join(log_dir, "app.log") # 简化逻辑
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-20:]
                    logs = "".join(lines)
            else: logs = "未找到日志文件"
            
            text = f"🧾 **最近系统日志 (20行)**\n\n```\n{logs}\n```"
            buttons = [[Button.inline("👈 返回上一级", "new_menu:system_hub")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"查看日志失败: {e}")

    async def show_version_info(self, event):
        """显示版本信息 (支持分页)"""
        try:
            from ..callback.modules.changelog_callback import show_changelog
            await show_changelog(event, page=1)
        except Exception as e:
            logger.error(f"显示版本信息失败: {e}")
            await self._render_from_text(event, f"❌ **显示版本信息失败**\n\n{e}", [[Button.inline("👈 返回上一级", "new_menu:help_guide")]])

system_menu = SystemMenu()
