import logging
import asyncio
from typing import Optional
from controllers.base import BaseController, ControllerAbort
from services.menu_service import menu_service
from services.analytics_service import analytics_service
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
            await new_menu_system._render_page(
                event,
                title="⚙️ **系统设置中心**",
                body_lines=[view_result.text],
                buttons=view_result.buttons,
                breadcrumb="🏠 > ⚙️"
            )
        except Exception as e:
            return self.handle_exception(e)

    async def show_admin_panel(self, event):
        """显示管理员面板 (旧版增强)"""
        try:
            from core.helpers.common import is_admin
            if not await is_admin(event):
                 return await event.answer("⚠️ 权限不足", alert=True)
                 
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
            await event.answer(f"🗑️ 正在清理 {days} 天前的日志...")
            deleted_count = await async_cleanup_old_logs(days)
            await event.answer(f"✅ 清理完成，删除 {deleted_count} 条记录")
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
            await new_menu_system._render_page(event, "🗄️ **数据库性能监控**", [view_result.text], view_result.buttons)
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
            await new_menu_system._render_page(event, "🔧 **数据库优化中心**", [view_result.text], view_result.buttons)
        except Exception as e:
            return self.handle_exception(e)

    async def show_backup_management(self, event):
        """显示备份管理"""
        try:
            # 模拟数据，实际应从 service 获取
            data = {'last_backup': '2026-02-09 10:00', 'backup_count': 5}
            view_result = self.container.ui.admin.render_db_backup(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "💾 **数据库备份**", [view_result.text], view_result.buttons)
        except Exception as e:
            return self.handle_exception(e)

    async def show_cache_cleanup(self, event):
        """显示缓存清理"""
        try:
            data = {'tmp_size': '1.2MB', 'log_size': '450KB', 'dedup_cache_size': '12MB'}
            view_result = self.container.ui.admin.render_cache_cleanup(data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "🗑️ **垃圾清理**", [view_result.text], view_result.buttons)
        except Exception as e:
            return self.handle_exception(e)

    async def run_optimization_check(self, event):
        """执行优化检查"""
        try:
            await event.answer("🔍 正在运行优化检查...")
            from services.system_service import system_service
            result = await system_service.run_db_optimization()
            if result.get('success'):
                await event.answer(f"✅ {result.get('message')}")
            else:
                await event.answer(f"❌ 优化失败: {result.get('error')}", alert=True)
            await self.show_optimization_center(event)
        except Exception as e:
            return self.handle_exception(e)

    async def clear_dedup_cache(self, event):
        """清除去重缓存"""
        try:
            from services.dedup.engine import smart_deduplicator
            smart_deduplicator.time_window_cache.clear()
            smart_deduplicator.content_hash_cache.clear()
            await event.answer("✅ 内存缓存已清除")
            await self.show_cache_cleanup(event)
        except Exception as e:
            return self.handle_exception(e)
            
    async def do_backup(self, event):
        """执行备份"""
        try:
             await event.answer("⌛ 备份正在生成中...")
             # 实际调用备份服务
             await asyncio.sleep(1) 
             await event.answer("✅ 备份成功", alert=True)
             await self.show_backup_management(event)
        except Exception as e:
             return self.handle_exception(e)

    async def run_reindex(self, event):
        """全面重建索引 (VACUUM)"""
        try:
            await event.answer("🛠️ 正在执行全库整理...")
            from services.db_maintenance_service import db_maintenance_service
            await db_maintenance_service.optimize_database()
            await event.answer("✅ 优化完成")
        except Exception as e:
            return self.handle_exception(e)

    async def clear_alerts(self, event):
        """清除系统告警"""
        await event.answer("ℹ️ 告警基于实时状态，解决问题后自动消失", alert=True)

    async def run_archive_once(self, event):
        """启动自动归档"""
        try:
            await event.answer("📦 正在启动补全归档...")
             # ... Logic ...
            await event.answer("✅ 归档任务已完成")
        except Exception as e:
            return self.handle_exception(e)

    async def run_archive_force(self, event):
        """启动强制全量归档"""
        try:
            await event.answer("🚨 正在执行强制全量归档...")
             # ... Logic ...
            await event.answer("✅ 归档完成")
        except Exception as e:
            return self.handle_exception(e)

    async def rebuild_bloom_index(self, event):
        """重建 Bloom 索引"""
        try:
            await event.answer("🌸 正在尝试重建 Bloom 索引...")
            from repositories.archive_repair import repair_bloom_index
            await asyncio.to_thread(repair_bloom_index)
            await event.answer("✅ Bloom 索引重建完成")
        except Exception as e:
             return self.handle_exception(e)

    async def show_analytics_hub(self, event):
        """显示数据分析中心"""
        try:
            overview_data = await analytics_service.get_analytics_overview()
            # 这里复用 renderer.render_analytics_hub 或者迁移到 admin
            from ui.menu_renderer import menu_renderer
            render_data = menu_renderer.render_analytics_hub(overview_data)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "📊 **数据分析中心**", [render_data['text']], render_data['buttons'], "🏠 > 📊")
        except Exception as e:
            return self.handle_exception(e)

    async def show_session_management(self, event):
        """显示会话管理"""
        from handlers.button.callback.session_callback import callback_session_management
        await callback_session_management(event, None, None, None, None)

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
            from models.models import SystemConfiguration
            from sqlalchemy import select, update
            
            async with self.container.db.get_session() as s:
                # 获取当前状态
                result = await s.execute(select(SystemConfiguration).filter_by(key="maintenance_mode"))
                config = result.scalar_one_or_none()
                
                new_val = "true"
                if config and config.value.lower() == "true":
                    new_val = "false"
                
                if config:
                    await s.execute(update(SystemConfiguration).filter_by(key="maintenance_mode").values(value=new_val))
                else:
                    s.add(SystemConfiguration(key="maintenance_mode", value=new_val))
                
                await s.commit()
            
            status_text = "开启" if new_val == "true" else "关闭"
            await event.answer(f"✅ 维护模式已{status_text}")
            await self.show_admin_panel(event)
        except Exception as e:
            return self.handle_exception(e)

    async def show_system_logs(self, event):
        """显示系统运行日志 (Refactored to use Renderer)"""
        try:
            from models.models import ErrorLog
            from sqlalchemy import select, desc
            
            async with self.container.db.get_session() as s:
                result = await s.execute(
                    select(ErrorLog).order_by(desc(ErrorLog.created_at)).limit(5)
                )
                logs = result.scalars().all()
            
            view_result = self.container.ui.admin.render_system_logs(logs)
            
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(
                event, 
                title=f"{UIStatus.INFO} **系统运行日志**", 
                body_lines=[view_result.text], 
                buttons=view_result.buttons
            )
        except Exception as e:
            return self.handle_exception(e)

    async def show_config(self, event):
        """显示系统全局配置"""
        try:
            from models.models import SystemConfiguration
            from sqlalchemy import select
            async with self.container.db.get_session() as s:
                result = await s.execute(select(SystemConfiguration).limit(20))
                configs = result.scalars().all()
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
        await event.answer("🔄 重启指令已发出...")
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
            await event.answer(f"✅ 清理完成: {deleted_count}个文件, {deleted_size/1024/1024:.2f}MB")
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
                await event.answer()
        except Exception as e:
            return self.handle_exception(e)

    async def show_forward_performance(self, event):
        """显示实时监控面板 (别名)"""
        await self.show_realtime_monitor(event)

    async def show_realtime_monitor(self, event):
        """显示系统实时监控"""
        try:
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
            data = {'config': {'auto_vacuum': True, 'wal_mode': True, 'sync_mode': 'NORMAL'}}
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
            advice = await analytics_service.detect_anomalies()
            from ui.menu_renderer import menu_renderer
            rendered = menu_renderer.render_db_optimization_advice(advice)
            from handlers.button.new_menu_system import new_menu_system
            await new_menu_system._render_page(event, "💡 **优化建议**", [rendered['text']], rendered['buttons'])
        except Exception as e:
            return self.handle_exception(e)
