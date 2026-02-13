import logging
from typing import Dict, Any
from telethon.tl.custom import Button
from ui.constants import UIStatus
from .base_renderer import BaseRenderer, ViewResult

logger = logging.getLogger(__name__)

class MainMenuRenderer(BaseRenderer):
    """主菜单渲染器 (UIRE-2.0)"""
    
    def render(self, stats: Dict[str, Any]) -> ViewResult:
        """渲染系统主页 (Phase 4)"""
        if not stats:
            return self.render_error("系统数据暂时不可用", detail="无法从统计服务获取实时数据")
            
        today = stats.get('today', {})
        dedup = stats.get('dedup', {})
        
        forwards = today.get('total_forwards', 0)
        cached = dedup.get('cached_signatures', 0)
        size_mb = today.get('total_size_bytes', 0) / 1024 / 1024
        saved_mb = today.get('saved_traffic_bytes', 0) / 1024 / 1024
        
        return (self.new_builder()
            .set_title("Telegram 智能中枢", icon="🌌")
            .add_section("今日数据看板", [], icon="📊")
            .add_status_grid({
                "转发消息": f"{forwards:,} 条",
                "拦截重复": f"{cached:,} 次",
                "节省流量": f"{saved_mb:.1f} MB",
                "消耗流量": f"{size_mb:.1f} MB"
            })
            .add_section("系统状态", "🟢 运行良好 | ⏳ 延迟: 低", icon="⚙️")
            .add_button("🔄 转发中心", "new_menu:forward_hub")
            .add_button("🧹 智能去重", "new_menu:dedup_hub")
            .add_button("📊 数据分析", "new_menu:analytics_hub")
            .add_button("⚙️ 系统设置", "new_menu:system_hub")
            .add_button("🔄 刷新", "new_menu:refresh_main_menu", icon="🔄")
            .add_button("📖 帮助", "new_menu:help_guide", icon="📖")
            .add_button("🔒 退出", "new_menu:exit", icon="❌")
            .build())

    def render_forward_hub(self, data: Dict[str, Any]) -> ViewResult:
        """渲染转发管理中心"""
        overview = data.get('overview', {})
        builder = self.new_builder()
        builder.set_title("转发管理中心", icon="🔄")
        builder.add_breadcrumb(["首页", "转发中心"])
        builder.add_section("概览", "全面管理您的转发规则、历史消息处理及全局筛选。")
        
        if overview:
            builder.add_status_grid({
                "今日转发": f"{overview.get('total_forwards', 0):,} 条",
                "数据传输": f"{overview.get('total_size_bytes', 0) / 1024 / 1024:.1f} MB",
                "活跃聊天": f"{overview.get('active_chats', 0)} 个"
            })
        
        builder.add_button("⚙️ 规则管理", "new_menu:forward_management")
        builder.add_button("🔗 多源管理", "new_menu:multi_source_management")
        builder.add_button("📋 历史处理", "new_menu:history_messages")
        builder.add_button("🔍 内容搜索", "new_menu:forward_search")
        builder.add_button("📊 详细统计", "new_menu:forward_stats_detailed")
        builder.add_button("🎛️ 全局筛选", "new_menu:global_forward_settings")
        builder.add_button("🚀 性能监控", "new_menu:forward_performance")
        builder.add_button("刷新", "new_menu:refresh_forward_hub", icon="🔄")
        builder.add_button("返回首页", "new_menu:main_menu", icon=UIStatus.BACK)
        builder.add_button("关闭菜单", "new_menu:close", icon="❌")
        return builder.build()

    def render_dedup_hub(self, data: Dict[str, Any]) -> ViewResult:
        """渲染智能去重中心"""
        config = data.get('config', {})
        stats = data.get('stats', {})
        
        return (self.new_builder()
            .set_title("智能去重中心", icon="🧹")
            .add_breadcrumb(["首页", "去重中心"])
            .add_section("策略状态", [], icon="📊")
            .add_status_grid({
                "时间窗口": f"{config.get('time_window_hours', 24)}h",
                "相似阈值": f"{config.get('similarity_threshold', 0.85):.0%}",
                "启用功能": "、".join(data.get('enabled_features', []))[:15]
            })
            .add_section("缓存统计", [], icon="💾")
            .add_status_grid({
                "内容签名": f"{stats.get('cached_signatures', 0):,}",
                "哈希条目": f"{stats.get('cached_content_hashes', 0):,}",
                "追踪会话": f"{stats.get('tracked_chats', 0)}"
            })
            .add_button("⏰ 时间设置", "new_menu:dedup_time_window")
            .add_button("🎯 相似调节", "new_menu:dedup_similarity")
            .add_button("🔐 哈希管理", "new_menu:dedup_content_hash")
            .add_button("📊 数据详情", "new_menu:dedup_statistics")
            .add_button("⚙️ 高级功能", "new_menu:dedup_advanced")
            .add_button("🗑️ 垃圾清理", "new_menu:dedup_cache_management")
            .add_button("返回主页", "new_menu:main_menu", icon=UIStatus.BACK)
            .add_button("关闭菜单", "new_menu:close", icon="❌")
            .build())

    def render_analytics_hub(self, data: Dict[str, Any]) -> ViewResult:
        """渲染数据分析中心"""
        overview = data.get('overview', {})
        
        builder = self.new_builder()
        builder.set_title("数据分析中心", icon="📊")
        builder.add_breadcrumb(["首页", "分析中心"])
        
        if overview:
            builder.add_section("转发趋势", f"今日: {overview.get('today_total', 0)} 条 | 昨日: {overview.get('yesterday_total', 0)} 条")
            builder.add_status_grid({
                "数据量": f"{overview.get('data_size_mb', 0):.1f} MB",
                "最热类型": data.get('top_type', {}).get('name', '暂无'),
                "活跃会话": data.get('top_chat', {}).get('name', 'N/A')
            })
        
        builder.add_button("📊 转发统计", "new_menu:forward_analytics")
        builder.add_button("⏱️ 实时监控", "new_menu:realtime_monitor")
        builder.add_button("🚨 异常扫描", "new_menu:anomaly_detection")
        builder.add_button("📈 性能剖析", "new_menu:performance_analysis")
        builder.add_button("🗄️ DB 监控", "new_menu:db_performance_monitor")
        builder.add_button("🔧 DB 优化", "new_menu:db_optimization_center")
        builder.add_button("📋 详细报告", "new_menu:detailed_analytics")
        builder.add_button("📤 导出 CSV", "new_menu:export_csv")
        builder.add_button("返回首页", "new_menu:main_menu", icon=UIStatus.BACK)
        builder.add_button("关闭中心", "new_menu:close", icon="❌")
        return builder.build()

    def render_forward_analytics(self, data: Dict[str, Any]) -> ViewResult:
        """渲染转发详细统计页面"""
        builder = self.new_builder()
        builder.set_title("转发详细统计", icon="📈")
        builder.add_breadcrumb(["首页", "分析中心", "转发统计"])
        
        # 1. 周期信息
        period = data.get('period', {})
        summary = data.get('summary', {})
        builder.add_section("统计概览", 
            f"📅 周期: {period.get('start_date', '?')} 至 {period.get('end_date', '?')}\n"
            f"✅ 总计转发: {summary.get('total_forwards', 0)} 条\n"
            f"❌ 失败次数: {summary.get('total_errors', 0)} 次\n"
            f"📊 日均转发: {summary.get('avg_daily_forwards', 0):.1f} 条"
        )
        
        # 2. 每日趋势 (简易列表)
        daily_stats = data.get('daily_stats', [])
        if daily_stats:
            trend_lines = []
            for d in daily_stats[-7:]: # 只显示最近 7 天
                date_label = d.get('date', '').split('-')[-1] # 只取日期部分
                total = d.get('total_forwards', 0)
                errors = d.get('error_count', 0)
                icon = "🔥" if total > 50 else "📈"
                trend_lines.append(f"{icon} {date_label}日: {total} 条 (失败 {errors})")
            builder.add_section("最近 7 日趋势", "\n".join(trend_lines))
        
        # 3. 热门规则
        top_rules = data.get('top_rules', [])
        if top_rules:
            rule_lines = []
            for r in top_rules[:5]:
                rule_lines.append(f"• ID {r.get('rule_id')}: {r.get('success_count', 0)} 条")
            builder.add_section("热门转发规则", "\n".join(rule_lines))

        builder.add_button("🔄 刷新数据", "new_menu:forward_analytics")
        builder.add_button("👈 返回分析中心", "new_menu:analytics_hub")
        builder.add_button("🏠 返回主菜单", "new_menu:main_menu")
        builder.add_button("❌ 关闭统计", "new_menu:close")
        
        return builder.build()

    def render_system_hub(self, data: Dict[str, Any]) -> ViewResult:
        """渲染系统设置中心"""
        res = data.get('system_resources', {})
        conf = data.get('config_status', {})
        
        return (self.new_builder()
            .set_title("系统管理中心", icon="⚙️")
            .add_breadcrumb(["首页", "系统设置"])
            .add_section("硬件资源", [], icon="🖥️")
            .add_status_grid({
                "运行时间": f"{res.get('uptime_hours', 0)}h",
                "CPU 负载": f"{res.get('cpu_percent', 0):.1f}%",
                "内存占用": f"{res.get('memory_percent', 0):.1f}%"
            })
            .add_section("模块健康度", [], icon="⚙️")
            .add_status_grid({
                "转发引擎": conf.get('forward_rules', 'ERR'),
                "智去中心": conf.get('smart_dedup', 'ERR'),
                "数据落盘": conf.get('data_recording', 'ERR')
            })
            .add_button("⚙️ 基础设置", "new_menu:system_settings")
            .add_button("💬 会话管理", "new_menu:session_management")
            .add_button("📋 系统概览", "new_menu:system_overview")
            .add_button("📊 系统状态", "new_menu:system_status")
            .add_button("🔧 高级配置", "new_menu:system_settings")
            .add_button("🗑️ 缓存清理", "new_menu:cache_cleanup")
            .add_button("📚 日志观察", "new_menu:log_viewer")
            .add_button("🔄 重启引擎", "new_menu:system_status")
            .add_button("🏢 归档一次", "new_menu:db_archive_once")
            .add_button("🔙 返回主菜单", "new_menu:main_menu")
            .add_button("❌ 关闭设置", "new_menu:close")
            .build())

    def render_help_guide(self) -> ViewResult:
        """渲染帮助说明页面"""
        return (self.new_builder()
            .set_title("系统操作指南", icon="📖")
            .add_breadcrumb(["首页", "使用帮助"])
            .add_section("核心功能", [
                "🔄 转发管理: 创建转发路径，历史消息补发。",
                "🧹 智能去重: 时间/相似度指纹过滤技术。",
                "📊 数据分析: 流量走势与转发漏斗模型。",
                "⚙️ 系统设置: 底层配置、日志与引擎维护。"
            ])
            .add_section("快速入门", "初次使用请先在“转发管理”中添加源与目标的关联规则。")
            .add_button("📚 详细文档", "new_menu:detailed_docs", icon="📖")
            .add_button("❓ 常见问题", "new_menu:faq", icon="❓")
            .add_button("🛠️ 获取支持", "new_menu:tech_support", icon="🛠️")
            .add_button("返回", "new_menu:main_menu", icon=UIStatus.BACK)
            .build())

    def render_faq(self) -> ViewResult:
        """渲染常见问题解答"""
        return (self.new_builder()
            .set_title("常见问题 FAQ", icon="❓")
            .add_section("如何建立转发？", "转发中心 -> 规则管理 -> 新建规则 -> 选择源与目标。")
            .add_section("内容重复了？", "检查去重策略是否开启，时间窗口是否足够长（建议24h）。")
            .add_section("转发很慢？", "系统默认 1s 延迟保护账号，可在高级设置中调整。")
            .add_button("返回帮助", "new_menu:help_guide", icon=UIStatus.BACK)
            .build())

    def render_detailed_docs(self) -> ViewResult:
        """渲染详细文档"""
        return (self.new_builder()
            .set_title("核心开发文档", icon="📖")
            .add_section("转发流模型", "Source -> Middleware (Filtering/Dedup/AI) -> Target")
            .add_section("媒体过滤", "支持按类型（Image/Video/File）及大小（MB）进行正则级匹配。")
            .add_section("智能增强", "集成 AI 进行 Prompt 处理与内容润色（需配置 API Key）。")
            .add_button("返回帮助", "new_menu:help_guide", icon=UIStatus.BACK)
            .build())
