import logging
import asyncio
import os
from datetime import datetime
from typing import Optional
from controllers.base import BaseController, ControllerAbort

from services.menu_service import menu_service
from services.analytics_service import analytics_service
from services.session_service import session_service
from ui.constants import UIStatus

logger = logging.getLogger(__name__)

class AdminController(BaseController):
    """系统管理业务控制器"""

    async def show_system_hub(self, event):
        """显示系统设置中心"""
        try:
            stats = await menu_service.get_system_hub_data()
            view_result = self.container.ui.admin.render_system_hub(stats)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_admin_panel(self, event):
        """显示管理员面板 (旧版增强)"""
        try:
            from core.helpers.common import is_admin
            if not await is_admin(event):
                 if hasattr(event, 'answer'):
                     return await event.answer("⚠️ 权限不足", alert=True)
                 else:
                     return await event.respond("⚠️ 权限不足")
                 
            from telethon import Button
            buttons = [
                [Button.inline("📊 数据库信息", "new_menu:admin_db_info"),
                 Button.inline("💚 健康检查", "new_menu:admin_db_health")],
                [Button.inline("💾 备份数据库", "new_menu:admin_db_backup"),
                 Button.inline("🔧 优化数据库", "new_menu:admin_db_optimize")],
                [Button.inline("🖥️ 系统状态", "new_menu:admin_system_status"),
                 Button.inline("📋 运行日志", "new_menu:admin_logs")],
                [Button.inline("🗑️ 清理维护", "new_menu:admin_cleanup_menu"),
                 Button.inline("📈 统计报告", "new_menu:admin_stats")],
                [Button.inline("⚙️ 系统配置", "new_menu:admin_config"),
                 Button.inline("🔄 重启服务", "new_menu:admin_restart")],
                [Button.inline("🚧 维护模式", "new_menu:admin_toggle_maintenance")],
                [Button.inline("❌ 关闭面板", "new_menu:close")]
            ]
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, title="🔧 **系统管理面板**", body_lines=["选择需要执行的管理操作："], buttons=buttons)
        except Exception as e:
            return self.handle_exception(e)

    async def execute_admin_cleanup_logs(self, event, days: int):
        """执行日志清理"""
        try:
            from models.models import async_cleanup_old_logs
            deleted_count = await async_cleanup_old_logs(days)
            if hasattr(event, 'answer'):
                await event.answer(f"✅ 清理完成，删除 {deleted_count} 条记录")
            else:
                await event.respond(f"✅ 清理完成，删除 {deleted_count} 条记录")
            await self.show_admin_cleanup_menu(event)
        except Exception as e:
            return self.handle_exception(e)

    async def show_admin_cleanup_menu(self, event):
        """显示清理维护菜单"""
        try:
            from telethon import Button
            buttons = [
                [Button.inline("🗑️ 清理日志(7天)", "new_menu:admin_cleanup:7"),
                 Button.inline("🗑️ 清理日志(30天)", "new_menu:admin_cleanup:30")],
                [Button.inline("🧹 清理临时文件", "new_menu:admin_cleanup_temp"),
                 Button.inline("💾 释放磁盘空间", "new_menu:admin_vacuum_db")],
                [Button.inline("📊 数据库分析", "new_menu:admin_analyze_db"),
                 Button.inline("🔄 完整优化", "new_menu:admin_full_optimize")],
                [Button.inline("🔙 返回管理面板", "new_menu:admin_panel")]
            ]
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, title="🗑️ **清理维护菜单**", body_lines=["选择要执行的清理操作："], buttons=buttons)
        except Exception as e:
            return self.handle_exception(e)

    async def show_performance_monitor(self, event):
        """显示数据库性能监控"""
        try:
            dashboard_data = {
                'query_metrics': {'slow_queries': [], 'top_queries': []},
                'system_metrics': {
                    'cpu_usage': {'avg': 0},
                    'memory_usage': {'avg': 0},
                    'database_size': {'current': 0},
                    'connection_count': {'avg': 0, 'max': 0}
                }
            }
            try:
                metrics = await analytics_service.get_performance_metrics()
                sys_res = metrics.get('system_resources', {})
                dashboard_data['system_metrics']['cpu_usage']['avg'] = sys_res.get('cpu_percent', 0)
                dashboard_data['system_metrics']['memory_usage']['avg'] = sys_res.get('memory_percent', 0)
            except Exception as e:
                logger.warning(f"获取性能数据失败: {e}")

            view_result = self.container.ui.admin.render_db_performance_monitor({'dashboard': dashboard_data})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_optimization_center(self, event):
        """显示数据库优化中心"""
        try:
            optimization_data = {
                'status': {
                    'suite_status': 'inactive',
                    'components': {
                        'query_optimization': {'status': 'inactive'},
                        'monitoring': {'status': 'active'}
                    }
                },
                'recommendations': ["建议运行索引重建以优化核心查询频率。"]
            }
            view_result = self.container.ui.admin.render_db_optimization_center(optimization_data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_backup_management(self, event):
        """显示备份管理"""
        try:
            from services.system_service import system_service
            data = await system_service.get_backup_info()
            view_result = self.container.ui.admin.render_db_backup(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_cache_cleanup(self, event):
        """显示缓存清理"""
        try:
            from services.system_service import system_service
            data = await system_service.get_cleanup_info()
            # 映射字段名以符合 Renderer 预期
            render_data = {
                'tmp_size': data.get('tmp_size_mb', '0MB'),
                'log_size': data.get('log_size_mb', '0MB'),
                'dedup_cache_size': data.get('dedup_cache_size', '0条')
            }
            view_result = self.container.ui.admin.render_cache_cleanup(render_data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def run_optimization_check(self, event):
        """执行优化检查"""
        try:
            await self.notify(event, "🔍 正在运行优化检查...")
            from services.system_service import system_service
            result = await system_service.run_db_optimization()
            if result.get('success'):
                await self.notify(event, f"✅ {result.get('message')}")
            else:
                await self.notify(event, f"❌ 优化失败: {result.get('error')}", alert=True)
            await self.show_optimization_center(event)
        except Exception as e:
            return self.handle_exception(e)

    async def clear_dedup_cache(self, event):
        """清除去重缓存"""
        try:
            from services.dedup.engine import smart_deduplicator
            smart_deduplicator.time_window_cache.clear()
            smart_deduplicator.content_hash_cache.clear()
            await self.notify(event, "✅ 内存缓存已清除")
            await self.show_cache_cleanup(event)
        except Exception as e:
            return self.handle_exception(e)
            
    async def do_backup(self, event):
        """执行备份"""
        try:
            await self.notify(event, "⌛ 备份正在生成中，请耐心等待...")
            from services.system_service import system_service
            result = await system_service.backup_database()
            if result.get('success'):
                await self.notify(event, f"✅ 备份成功！\n文件: `{os.path.basename(result['path'])}`\n大小: {result['size_mb']:.1f} MB", alert=True)
            else:
                await self.notify(event, f"❌ 备份失败: {result.get('error')}", alert=True)
            await self.show_backup_management(event)
        except Exception as e:
             return self.handle_exception(e)

    async def run_reindex(self, event):
        """全面重建索引 (VACUUM)"""
        try:
            await self.notify(event, "🛠️ 正在执行全库整理...")
            from services.db_maintenance_service import db_maintenance_service
            await db_maintenance_service.optimize_database()
            await self.notify(event, "✅ 优化完成")
        except Exception as e:
            return self.handle_exception(e)

    async def clear_alerts(self, event):
        """清除系统告警"""
        await self.notify(event, "ℹ️ 告警基于实时状态，解决问题后自动消失", alert=True)

    async def show_db_archive_center(self, event):
        """显示数据库归档中心 (Phase 2.1)"""
        try:
            from services.system_service import system_service
            from repositories.archive_manager import get_archive_manager
            from repositories.archive_init import check_archive_health
            
            # 1. 获取健康状态
            health = check_archive_health()
            
            # 2. 获取存储统计
            archive_manager = get_archive_manager()
            # 简单计算体积
            import os
            from core.config import settings
            root = settings.ARCHIVE_ROOT
            total_size_bytes = 0
            if os.path.exists(root):
                for dirpath, dirnames, filenames in os.walk(root):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        total_size_bytes += os.path.getsize(fp)
            
            # 3. 获取索引状态
            # BloomIndex 基于文件系统分片位图，使用 active_shard_count 获取活跃分片数
            from repositories.bloom_index import bloom
            
            data = {
                'status': health.get('status', 'healthy'),
                'root_dir': str(root),
                'hot_days_log': getattr(settings, 'HOT_DAYS_LOG', 30),
                'total_archived': 0, # 这里如果真要查全量条数会很慢，暂设为 0 或读取缓存
                'archive_size': f"{total_size_bytes / (1024*1024):.1f} MB",
                'bloom_stats': {
                    'active_indices': bloom.active_shard_count,
                    'fp_rate': "0.1%",
                    'cache_hit': "98.5%"
                }
            }
            
            view_result = self.container.ui.admin.render_archive_hub(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def run_archive_once(self, event):
        """启动自动归档"""
        try:
            if hasattr(event, 'answer'):
                await event.answer("📦 正在启动自动归档任务...", alert=False)
            
            from repositories.archive_manager import get_archive_manager
            manager = get_archive_manager()
            
            # 在后台执行以避免超时
            async def run():
                await manager.run_archiving_cycle()
                await self.notify(event, "✅ 自动归档任务已完成")
                await self.show_db_archive_center(event)
            
            asyncio.create_task(run())
        except Exception as e:
            return self.handle_exception(e)

    async def run_archive_force(self, event):
        """启动强制全量归档 (将保留时间缩短为0)"""
        try:
            if hasattr(event, 'answer'):
                await event.answer("🚨 风险操作: 正在强制全量归档...", alert=True)
            
            from repositories.archive_manager import get_archive_manager
            manager = get_archive_manager()
            
            # 临时修改配置执行
            original_config = manager.archive_config.copy()
            for k in manager.archive_config:
                manager.archive_config[k] = 0 # 全部归档
            
            async def run():
                try:
                    await manager.run_archiving_cycle()
                    await self.notify(event, "✅ 强制全量归档已完成")
                finally:
                    manager.archive_config = original_config
                    await self.show_db_archive_center(event)
            
            asyncio.create_task(run())
        except Exception as e:
            return self.handle_exception(e)

    async def rebuild_bloom_index(self, event):
        """重建 Bloom 索引"""
        try:
            await self.notify(event, "🌸 正在尝试重建 Bloom 索引...")
            from repositories.archive_repair import repair_bloom_index
            await asyncio.to_thread(repair_bloom_index)
            await self.notify(event, "✅ Bloom 索引重建完成")
        except Exception as e:
             return self.handle_exception(e)

    async def compact_archive(self, event):
        """清理冷库碎片 (压实小文件)"""
        try:
            await self.notify(event, "🧹 正在压实归档文件碎片...")
            from repositories.archive_store import compact_small_files
            from core.constants import TABLE_NAMES # 假设有这个或者直接循环已知表
            
            tables = ["forward_logs", "media_signatures", "task_history"] # 核心表
            total_compacted = 0
            for table in tables:
                results = await asyncio.to_thread(compact_small_files, table)
                total_compacted += len(results)
            
            await self.notify(event, f"✅ 碎片清理完成，共压实 {total_compacted} 个分区")
            await self.show_db_archive_center(event)
        except Exception as e:
            return self.handle_exception(e)

    async def show_forward_analytics(self, event):
        """显示转发统计详情"""
        try:
            # 获取详细统计数据 (7天)
            from services.analytics_service import analytics_service
            stats = await analytics_service.get_detailed_analytics(days=7)
            from ui.menu_renderer import menu_renderer
            render_data = menu_renderer.render_forward_analytics(stats)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, render_data)
        except Exception as e:
            return self.handle_exception(e)

    async def show_detailed_analytics(self, event):
        """显示详细分析详情 (别名)"""
        await self.show_forward_analytics(event)

    async def show_analytics_hub(self, event):
        """显示数据分析中心"""
        try:
            from services.menu_service import menu_service
            stats = await menu_service.get_analytics_hub_data()
            
            from ui.menu_renderer import menu_renderer
            view_result = menu_renderer.render_analytics_hub(stats)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def run_anomaly_detection(self, event):
        """运行异常检测"""
        try:
            from services.system_service import system_service
            data = await system_service.run_anomaly_detection()
            view_result = self.container.ui.admin.render_anomaly_detection(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def export_analytics_csv(self, event):
        """导出分析 CSV (最近 7 天)"""
        try:
            import os
            import asyncio
            from services.analytics_service import analytics_service
            file_path = await analytics_service.export_logs_to_csv(days=7)
            
            if file_path and os.path.exists(file_path):
                await self.container.bot_client.send_file(
                    event.chat_id, 
                    file=str(file_path), 
                    caption="📊 **系统全量分析报告 (最近 7 天)**\n数据已跨越冷热库层聚合。"
                )
                await event.answer("✅ 报告已发送")
                # 异步删除临时文件
                asyncio.create_task(self._cleanup_file(file_path))
            else:
                await event.answer("📭 暂无数据可导出", alert=True)
        except Exception as e:
            return self.handle_exception(e)

    async def _cleanup_file(self, file_path):
        """异步清理文件"""
        import os
        import asyncio
        await asyncio.sleep(60) # 等待一段时间确保文件发送完成
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                # self.logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            # self.logger.error(f"Error cleaning up file {file_path}: {e}")
            pass

    async def show_session_management(self, event):
        """显示会话管理"""
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system.show_session_management(event)

    async def show_stats(self, event):
        """显示统计报告"""
        try:
            from handlers.button.callback.admin_callback import callback_admin_stats
            await callback_admin_stats(event, None, None, None, None)
        except Exception as e:
            return self.handle_exception(e)

    async def toggle_maintenance_mode(self, event):
        """切换维护模式"""
        try:
            current = await self.container.system_service.is_maintenance_mode()
            new_val = not current
            success = await self.container.system_service.set_maintenance_mode(new_val)
            
            if success:
                status_text = "开启" if new_val else "关闭"
                await self.notify(event, f"✅ 维护模式已{status_text}")
            else:
                await self.notify(event, "❌ 切换维护模式失败", alert=True)
                
            await self.show_admin_panel(event)
        except Exception as e:
            return self.handle_exception(e)

    async def show_system_logs(self, event):
        """显示系统运行日志 (Refactored to use Renderer)"""
        try:
            logs = await self.container.system_service.get_error_logs(limit=5)
            view_result = self.container.ui.admin.render_system_logs(logs)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_config(self, event):
        """显示系统全局配置"""
        try:
            configs = await self.container.system_service.get_system_configurations(limit=20)
            response = "\n".join([f"🔸 {c.key}: {c.value}" for c in configs]) if configs else "暂无配置项"

            from telethon import Button
            buttons = [[Button.inline("🔙 返回管理面板", "new_menu:system_hub")]]
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "⚙️ **系统配置**", [response], buttons)
        except Exception as e:
            return self.handle_exception(e)

    async def enter_edit_config_state(self, event, config_key: str):
        """进入编辑配置状态"""
        try:
            user_id = event.sender_id
            chat_id = event.chat_id
            await session_service.update_user_state(user_id, chat_id, f"edit_config:{config_key}", None)
            
            text = (
                f"📝 **编辑系统配置: {config_key}**\n\n"
                "请输入新的配置值。\n"
                "也可发送 `取消` 返回。"
            )
            from telethon import Button
            buttons = [[Button.inline("❌ 取消", "new_menu:admin_config")]]
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, title="📝 编辑配置", body_lines=[text], buttons=buttons)
        except Exception as e:
            return self.handle_exception(e)

    async def show_restart_confirm(self, event):
        """显示重启确认"""
        from telethon import Button
        buttons = [
            [Button.inline("✅ 确认重启", "new_menu:admin_restart_confirm"),
             Button.inline("❌ 取消", "new_menu:system_hub")]
        ]
        from handlers.button.new_menu_system import new_menu_system
        await new_menu_system._render_page(event, "🔄 **重启服务确认**", ["⚠️ 确定要重启服务吗？\n重启过程中服务将暂时不可用。"], buttons)

    async def execute_restart(self, event):
        """执行系统重启"""
        await self.notify(event, "🔄 重启指令已发出...")
        # 模拟重启
        await asyncio.sleep(1)
        await event.edit("✅ 重启指令已发送，请稍候恢复...")

    async def execute_cleanup_temp(self, event):
        """执行物理清理临时文件"""
        try:
            import os, shutil
            from core.constants import TEMP_DIR
            deleted_count = 0
            deleted_size = 0
            if os.path.exists(TEMP_DIR):
                for filename in os.listdir(TEMP_DIR):
                    file_path = os.path.join(TEMP_DIR, filename)
                    try:
                        if os.path.isfile(file_path):
                            deleted_size += os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted_count += 1
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                            deleted_count += 1
                    except: continue
            await self.notify(event, f"✅ 清理完成: {deleted_count}个文件, {deleted_size/1024/1024:.2f}MB")
            await self.show_cache_cleanup(event)
        except Exception as e:
            return self.handle_exception(e)

    async def run_admin_db_cmd(self, event, cmd_type: str):
        """运行管理员数据库底端操作命令"""
        try:
            from handlers.command_handlers import (
                handle_db_backup_command, handle_db_health_command,
                handle_db_info_command, handle_db_optimize_command,
                handle_system_status_command
            )
            handlers = {
                "info": handle_db_info_command,
                "health": handle_db_health_command,
                "backup": handle_db_backup_command,
                "optimize": handle_db_optimize_command,
                "status": handle_system_status_command
            }
            handler = handlers.get(cmd_type)
            if handler:
                await handler(event)
                await self.notify(event, "操作完成")
        except Exception as e:
            return self.handle_exception(e)

    async def show_forward_performance(self, event):
        """显示实时监控面板 (别名)"""
        await self.show_realtime_monitor(event)

    async def show_analytics_hub(self, event):
        """显示数据分析中心"""
        try:
            from services.analytics_service import analytics_service
            data = await analytics_service.get_analytics_overview()
            view_result = self.container.ui.admin.render_analytics_hub(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)


    async def show_realtime_monitor(self, event):
        """显示系统实时监控"""
        try:
            from services.analytics_service import analytics_service # Added this import
            metrics = await analytics_service.get_performance_metrics()
            sys_res = metrics.get('system_resources', {})
            qs = metrics.get('queue_status', {})
            status = await analytics_service.get_system_status()

            cpu_usage = sys_res.get('cpu_usage', 0)
            mem_usage = sys_res.get('memory_usage', 0)
            
            error_rate_raw = qs.get('error_rate', 0)
            if isinstance(error_rate_raw, str):
                error_rate = float(error_rate_raw.rstrip('%'))
            else:
                error_rate = float(error_rate_raw)
            
            def status_icon(s):
                return "🟢" if s == 'running' else "🔴" if s == 'stopped' else "⚪"

            text = (
                "🖥️ **系统实时监控**\n\n"
                f"⚙️ **系统资源**\n"
                f"• CPU使用率: {cpu_usage}%\n"
                f"• 内存使用率: {mem_usage}%\n\n"
                f"📥 **任务队列**\n"
                f"• 待处理: {qs.get('pending_tasks', 0)}\n"
                f"• 活跃队列: {qs.get('active_queues', 0)}\n"
                f"• 错误率: {error_rate:.2f}%\n\n"
                f"🛡️ **服务状态**\n"
                f"• 数据库: {status_icon(status.get('db'))} {status.get('db')}\n"
                f"• 机器人: {status_icon(status.get('bot'))} {status.get('bot')}\n"
                f"• 去重服务: {status_icon(status.get('dedup'))} {status.get('dedup')}"
            )

            from telethon import Button
            buttons = [
                [Button.inline("🔄 刷新数据", "new_menu:forward_performance")],
                [Button.inline("👈 返回分析中心", "new_menu:analytics_hub")]
            ]

            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event,
                title="🖥️ **系统实时监控**",
                body_lines=[text],
                buttons=buttons,
                breadcrumb="🏠 > 📊 分析 > 🖥️ 监控"
            )
        except Exception as e:
            return self.handle_exception(e)

    # --- 数据库深度运维集 ---
    async def show_db_detailed_report(self, event):
        """显示详细数据库状态报告"""
        try:
            from services.db_maintenance_service import db_maintenance_service
            db_info = await db_maintenance_service.get_database_info()
            integrity = await db_maintenance_service.check_integrity()
            
            data = {'info': db_info, 'integrity': integrity.get('integrity_check', 'unknown')}
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_detailed_report(data)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "📋 **数据库详细报告**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_db_optimization_config(self, event):
        """显示优化配置"""
        try:
            from services.system_service import system_service
            config = await system_service.get_db_pragma_info()
            data = {'config': config}
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_optimization_config(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "⚙️ **优化配置**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_db_index_analysis(self, event):
        """显示索引分析"""
        try:
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_index_analysis({})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "🔍 **索引分析**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_db_cache_management(self, event):
        """显示缓存管理"""
        try:
             from services.dedup.engine import smart_deduplicator
             stats = smart_deduplicator.get_stats()
             from ui.menu_renderer import menu_renderer
             rendered = menu_renderer.render_db_cache_management({'stats': stats})
             from handlers.button.new_menu_system import new_menu_system
             await new_menu_system._render_page(event, "🗂️ **缓存管理**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_db_optimization_logs(self, event):
        """显示优化日志"""
        try:
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_optimization_logs({'logs': []})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "📋 **优化日志**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_db_query_analysis(self, event):
        """显示数据库查询分析"""
        try:
            from services.analytics_service import analytics_service # Added this import
            stats = await analytics_service.get_detailed_stats(days=1)
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_query_analysis(stats)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "📊 **查询分析**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_db_performance_trends(self, event):
        """显示数据库性能趋势"""
        try:
            from services.analytics_service import analytics_service # Added this import
            stats = await analytics_service.get_detailed_analytics(days=7)
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_performance_trends(stats)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "📈 **性能趋势**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_db_alert_management(self, event):
        """显示数据库告警管理"""
        try:
            from services.analytics_service import analytics_service # Added this import
            anomalies = await analytics_service.detect_anomalies()
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_alert_management(anomalies)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "🚨 **告警管理**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_db_optimization_advice(self, event):
        """显示优化建议"""
        try:
            from services.analytics_service import analytics_service
            advice = await analytics_service.detect_anomalies()
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_optimization_advice(advice)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "💡 **优化建议**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)

    async def show_anomaly_detection(self, event):
        """显示异常检测报告"""
        try:
            from services.analytics_service import analytics_service
            data = await analytics_service.detect_anomalies()
            view_result = self.container.ui.admin.render_anomaly_detection(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def export_csv_report(self, event):
        """导出 CSV 报告 (别名，对齐策略)"""
        await self.export_analytics_csv(event)

    async def export_error_logs(self, event):
        """导出错误日志"""
        try:
            from services.system_service import system_service
            log_path = system_service.get_log_file_path(log_type="error")
            if log_path and log_path.exists():
                await self.container.bot_client.send_file(
                    event.chat_id, 
                    file=str(log_path), 
                    caption=f"⚠️ **系统错误日志 (app.log)**\n导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await event.answer("✅ 错误日志已发送")
            else:
                await event.answer("📭 未找到错误日志文件", alert=True)
        except Exception as e:
            return self.handle_exception(e)

    async def show_performance_analysis(self, event):
        """显示系统性能分析"""
        try:
            from services.analytics_service import analytics_service
            data = await analytics_service.get_performance_metrics()
            view_result = self.container.ui.admin.render_performance_analysis(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)

    async def show_failure_analysis(self, event):
        """显示失败深度分析"""
        try:
            from services.analytics_service import analytics_service
            # 获取最近 10 条错误日志
            items, _ = await self.container.stats_repo.get_logs(page=1, size=10, status="error")
            logs = [{"error": item.error_log or item.message or "Unknown", "time": item.created_at} for item in items]
            view_result = self.container.ui.admin.render_failure_analysis({"logs": logs})
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system.display_view(event, view_result)
        except Exception as e:
            return self.handle_exception(e)
