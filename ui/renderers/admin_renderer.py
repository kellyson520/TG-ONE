from typing import Dict, Any, List
from telethon.tl.custom import Button
from .base_renderer import BaseRenderer, ViewResult
from ui.constants import UIStatus

class AdminRenderer(BaseRenderer):
    """系统管理与监控渲染器"""

    def render_system_hub(self, data: Dict[str, Any]) -> ViewResult:
        """渲染系统设置中心主页"""
        return (self.new_builder()
            .set_title("系统设置中心", icon=UIStatus.SETTINGS)
            .add_breadcrumb(["首页", "系统中心"])
            .add_section("基础能力管理", "管理项目的数据库备份、垃圾清理及底层存储优化。", icon="🛠️")
            .add_status_grid({
                "数据库状态": ("正常", UIStatus.SUCCESS),
                "存储占用": data.get('db_size', 'Unknown'),
                "核心引擎": ("运行中", UIStatus.SUCCESS)
            })
            .add_button("数据库维护", action="new_menu:db_optimization_center", icon=UIStatus.SYNC)
            .add_button("性能监控", action="new_menu:db_performance_monitor", icon=UIStatus.SEARCH)
            .add_button("备份管理", action="new_menu:db_backup", icon=UIStatus.ADD)
            .add_button("垃圾清理", action="new_menu:cache_cleanup", icon=UIStatus.TRASH)
            .add_button("会话管理", action="new_menu:session_management", icon=UIStatus.DOT)
            .add_button("系统日志", action="new_menu:system_logs", icon=UIStatus.INFO)
            .add_button("返回主菜单", action="new_menu:main_menu", icon=UIStatus.BACK)
            .build())

    def render_db_performance_monitor(self, data: Dict[str, Any]) -> ViewResult:
        """渲染数据库性能监控视图"""
        metrics = data.get('dashboard', {}).get('system_metrics', {})
        cpu = metrics.get('cpu_usage', {}).get('avg', 0)
        mem = metrics.get('memory_usage', {}).get('avg', 0)
        
        return (self.new_builder()
            .set_title("数据库性能监控", icon=UIStatus.SEARCH)
            .add_breadcrumb(["首页", "系统", "性能监控"])
            .add_section("实时资源占用", [], icon="📊")
            .add_status_grid({
                "CPU 负载": f"{cpu}%",
                "内存占用": f"{mem}%",
                "连接数": metrics.get('connection_count', {}).get('avg', 0)
            })
            .add_section("查询效率分析", [
                f"慢查询 (24h): {len(data.get('dashboard', {}).get('query_metrics', {}).get('slow_queries', []))} 条",
                f"读写配比: {data.get('rw_ratio', 'N/A')}"
            ], icon="⚡")
            .add_button("刷新面板", action="new_menu:refresh_db_performance", icon=UIStatus.SYNC)
            .add_button("查询分析", action="new_menu:db_query_analysis", icon=UIStatus.STAR)
            .add_button("性能趋势", action="new_menu:db_performance_trends", icon=UIStatus.INFO)
            .add_button("告警管理", action="new_menu:db_alert_management", icon=UIStatus.ERROR)
            .add_button("返回系统中心", action="new_menu:system_hub", icon=UIStatus.BACK)
            .build())

    def render_db_optimization_center(self, data: Dict[str, Any]) -> ViewResult:
        """渲染数据库优化中心视图"""
        status = data.get('status', {})
        suite_status = status.get('suite_status', 'inactive')
        progress = data.get('progress', 100) # 模拟进度
        
        return (self.new_builder()
            .set_title("数据库优化中心", icon="🔧")
            .add_breadcrumb(["首页", "系统", "优化"])
            .add_progress_bar("分析完整度", progress)
            .add_section("服务巡检结果", [], icon="🎯")
            .add_status_grid({
                "自动优化": ("已开启", UIStatus.SUCCESS) if suite_status == 'active' else ("未开启", UIStatus.ERROR),
                "索引完整性": ("良好", UIStatus.SUCCESS)
            })
            .add_section("专家建议", data.get('recommendations', ['暂无显著优化建议，系统运行良好。']), icon="💡")
            .add_button("启动巡检", action="new_menu:run_db_optimization_check", icon=UIStatus.ADD)
            .add_button("重建索引", action="new_menu:db_reindex", icon=UIStatus.SYNC)
            .add_button("归档中心", action="new_menu:db_archive_center", icon=UIStatus.FILTER)
            .add_button("优化配置", action="new_menu:db_optimization_config", icon=UIStatus.SETTINGS)
            .add_button("返回系统中心", action="new_menu:system_hub", icon=UIStatus.BACK)
            .build())

    def render_system_logs(self, logs: List[Any]) -> ViewResult:
        """渲染系统运行日志预览 (Phase 3.6)"""
        builder = self.new_builder()
        builder.set_title("系统运行日志", icon="📋")
        builder.add_breadcrumb(["首页", "运行日志"])
        
        if not logs:
            builder.add_section("状态", "✨ 暂无错误日志记录", icon=UIStatus.INFO)
        else:
            for log in logs:
                # 按级别自动映射图标 (Level Coloring)
                level = str(log.level).upper()
                icon = "⚪"
                if "ERROR" in level: icon = "🔴"
                elif "WARN" in level: icon = "🟡"
                elif "INFO" in level: icon = "🔵"
                
                builder.add_section(
                    f"{icon} {level} | {log.created_at.strftime('%H:%M:%S') if hasattr(log.created_at, 'strftime') else log.created_at}", 
                    [
                        f"模块: `{log.module or 'Core'}`",
                        f"消息: {log.message[:150]}"
                    ]
                )
                
        builder.add_button("刷新", "new_menu:admin_logs", icon="🔄")
        builder.add_button("返回管理面板", "new_menu:admin_panel", icon="🔙")
        return builder.build()

    def render_db_backup(self, data: Dict[str, Any]) -> ViewResult:
        """渲染备份管理视图"""
        return (self.new_builder()
            .set_title("数据库备份管理", icon=UIStatus.ADD)
            .add_breadcrumb(["首页", "系统", "备份"])
            .add_section("操作说明", "您可以手动触发现有数据库的备份，或者管理历史备份包。")
            .add_status_grid({
                "最后备份": data.get('last_backup', '从未'),
                "备份总数": data.get('backup_count', 0)
            })
            .add_button("立即执行备份", action="new_menu:do_backup", icon=UIStatus.SUCCESS)
            .add_button("浏览历史备份", action="new_menu:view_backups", icon="📂")
            .add_button("返回系统中心", action="new_menu:system_hub", icon=UIStatus.BACK)
            .build())

    def render_cache_cleanup(self, data: Dict[str, Any]) -> ViewResult:
        """渲染缓存清理视图"""
        return (self.new_builder()
            .set_title("缓存与空间清理", icon=UIStatus.TRASH)
            .add_breadcrumb(["首页", "系统", "清理"])
            .add_section("扫描详情", "此操作将扫描并删除临时文件、会话快照和过期日志。", icon="🧹")
            .add_status_grid({
                "临时导出文件": data.get('tmp_size', '0B'),
                "历史流日志": data.get('log_size', '0B'),
                "去重内存索引": data.get('dedup_cache_size', '0B')
            })
            .add_button("深度清理", action="new_menu:do_cleanup", icon="🔥")
            .add_button("清除去重缓存", action="new_menu:clear_dedup_cache", icon=UIStatus.FILTER)
            .add_button("返回系统中心", action="new_menu:system_hub", icon=UIStatus.BACK)
            .build())
