from typing import Dict, Any
from telethon.tl.custom import Button
from .base_renderer import BaseRenderer

class SettingsRenderer(BaseRenderer):
    """设置与分析渲染器 (UIRE-2.0)"""
    
    def render_dedup_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染去重设置页面 (Phase 4.4)"""
        config = data.get('config', {})
        enabled = config.get('enable_time_window', True)
        hours = config.get('time_window_hours', 24)
        
        return (self.new_builder()
            .set_title("去重策略设置", icon="⏰")
            .add_breadcrumb(["首页", "分析", "时间去重"])
            .add_section("策略说明", "时间窗口去重会在指定时间内避免转发相同指纹的内容，防止刷屏。")
            .add_status_grid({
                "当前状态": ("已启用", UIStatus.SUCCESS) if enabled else ("已禁用", UIStatus.ERROR),
                "时间窗口": "永久窗口" if int(hours) <= 0 else f"{hours} 小时"
            })
            .add_section("快捷设置建议", [
                "1小时: 适合高频社交转发",
                "24小时: 推荐平衡模式",
                "7天: 严格控制重复内容"
            ], icon="💡")
            .add_button(f"{'🔴 关闭去重' if enabled else '🟢 开启去重'}", f"new_menu:toggle_time_window:{not enabled}")
            .add_button("1时", "new_menu:set_time_window:1")
            .add_button("6时", "new_menu:set_time_window:6")
            .add_button("12时", "new_menu:set_time_window:12")
            .add_button("24时⭐", "new_menu:set_time_window:24")
            .add_button("72时", "new_menu:set_time_window:72")
            .add_button("7天", "new_menu:set_time_window:168")
            .add_button("♾ 永久", "new_menu:set_time_window:0")
            .add_button("返回中心", "new_menu:dedup_hub", icon=UIStatus.BACK)
            .build())

    def render_anomaly_detection(self, data: Dict[str, Any]) -> ViewResult:
        """渲染异常检测页面"""
        health_score = data.get('health_score', 75.0)
        anomalies = data.get('anomalies', [])
        
        builder = self.new_builder()
        builder.set_title("智能异常检测", icon="🚨")
        builder.add_breadcrumb(["首页", "分析", "异常扫描"])
        
        builder.add_progress_bar("系统运行健康度", health_score)
        
        if anomalies:
            lines = [f"{a['icon']} {a['message']}" for a in anomalies]
            builder.add_section("发现异常项", lines, icon="🔍")
        else:
            builder.add_section("状态扫描", "✅ 系统运行平稳，未发现潜在异常。", icon=UIStatus.SUCCESS)
            
        builder.add_section("专家建议操作", data.get('recommendations', ["无建议"]), icon="💡")
        
        builder.add_button("重新扫描", "new_menu:anomaly_detection", icon="🔄")
        builder.add_button("返回分析中心", "new_menu:analytics_hub", icon=UIStatus.BACK)
        return builder.build()

    def render_performance_metrics(self, data: Dict[str, Any]) -> ViewResult:
        """渲染系统性能全景视图"""
        sys = data.get('system_resources', {})
        perf = data.get('performance', {})
        qs = data.get('queue_status', {})
        
        return (self.new_builder()
            .set_title("系统性能全景", icon="⏱️")
            .add_breadcrumb(["首页", "监控", "全景"])
            .add_section("物理资源 (OS)", [], icon="🖥️")
            .add_status_grid({
                "CPU 负载": f"{sys.get('cpu_percent', 0):.1f}%",
                "内存占用": f"{sys.get('memory_percent', 0):.1f}%",
                "进程状态": sys.get('status', 'RUNNING').upper()
            })
            .add_section("应用吞吐 (APP)", [], icon="📊")
            .add_status_grid({
                "转发成功率": f"{perf.get('success_rate', 0):.1f}%",
                "平均响应": f"{perf.get('avg_response_time', 0):.2f}s",
                "实时 TPS": f"{perf.get('current_tps', 0):.1f}"
            })
            .add_section("队列积压 (MQ)", [
                f"活动队列: {qs.get('active_queues', '0')}",
                f"平均延迟: {qs.get('avg_delay', '0s')}"
            ], icon="📤")
            .add_button("刷新面板", "new_menu:realtime_monitor", icon="🔄")
            .add_button("详细报告", "new_menu:detailed_performance", icon="📈")
            .add_button("性能调控", "new_menu:performance_tuning", icon="⚙️")
            .add_button("返回中心", "new_menu:analytics_hub", icon=UIStatus.BACK)
            .build())

    def render_db_performance_monitor(self, data: Dict[str, Any]) -> ViewResult:
        """渲染数据库性能监控面板"""
        dashboard = data.get('dashboard', {})
        metrics = dashboard.get('query_metrics', {})
        sys = dashboard.get('system_metrics', {})
        
        builder = self.new_builder()
        builder.set_title("数据库运维监控", icon="🗄️")
        builder.add_breadcrumb(["分析", "DB 监控"])
        
        builder.add_section("查询深度分析", [], icon="🐌")
        slow_queries = metrics.get('slow_queries', [])
        if slow_queries:
            lines = [f"• {q.get('duration', 0):.1f}s | {q.get('sql', '')[:40]}..." for q in slow_queries[:2]]
            builder.add_section("慢查询摘要", lines)
        else:
            builder.add_section("慢查询状态", "✅ 近 24h 无慢查询记录")
            
        builder.add_section("运行时指标", [], icon="💻")
        builder.add_status_grid({
            "DB 大小": f"{sys.get('database_size', {}).get('current', 0) / (1024*1024):.1f} MB",
            "活跃连接": f"{sys.get('connection_count', {}).get('avg', 0):.0f}",
            "健康状态": "良好" if not dashboard.get('alerts') else "有告警"
        })
        
        builder.add_button("查询分析", "new_menu:db_query_analysis", icon="📊")
        builder.add_button("性能趋势", "new_menu:db_performance_trends", icon="📈")
        builder.add_button("告警中心", "new_menu:db_alert_management", icon="🚨")
        builder.add_button("刷新", "new_menu:db_performance_refresh", icon="🔄")
        builder.add_button("返回", "new_menu:analytics_hub", icon=UIStatus.BACK)
        return builder.build()

    def render_db_optimization_center(self, data: Dict[str, Any]) -> ViewResult:
        """渲染数据库优化中心"""
        status = data.get('status', {})
        
        builder = self.new_builder()
        builder.set_title("数据库智优中心", icon="🔧")
        builder.add_breadcrumb(["分析", "优化中心"])
        
        builder.add_section("引擎状态", f"当前自动化优化系统: {'✅ 已激活' if status.get('suite_status') == 'active' else '❌ 未激活'}")
        
        recs = data.get('recommendations', [])
        if recs:
            lines = [f"• {r.get('title')}" for r in recs[:3]]
            builder.add_section("专家建议", lines, icon="💡")
            
        builder.add_button("启动检查", "new_menu:run_db_optimization_check", icon="🔍")
        builder.add_button("优化配置", "new_menu:db_optimization_config", icon="⚙️")
        builder.add_button("索引分析", "new_menu:db_index_analysis", icon="🔍")
        builder.add_button("缓存管理", "new_menu:db_cache_management", icon="🗂️")
        builder.add_button("返回中心", "new_menu:analytics_hub", icon=UIStatus.BACK)
        return builder.build()

    def render_db_query_analysis(self, data: Dict[str, Any]) -> ViewResult:
        """渲染查询分析页"""
        top_rules = data.get('top_rules', [])
        
        builder = self.new_builder()
        builder.set_title("高频数据路径分析", icon="📊")
        
        if top_rules:
            lines = [f"• `{r.get('name')}`: {r.get('count')} 写入" for r in top_rules[:5]]
            builder.add_section("最活跃转发规则", lines, icon="🔥")
        else:
            builder.add_section("统计信息", "数据收集中...")
            
        builder.add_button("刷新", "new_menu:db_query_analysis", icon="🔄")
        builder.add_button("返回监控", "new_menu:db_performance_monitor", icon="👈")
        return builder.build()

    def render_db_performance_trends(self, data: Dict[str, Any]) -> ViewResult:
        """渲染性能趋势页"""
        history = data.get('daily_stats', [])
        builder = self.new_builder()
        builder.set_title("全库写入趋势 (7D)", icon="📈")
        
        if history:
            # 这里原本有简单的条形图，MenuBuilder 以后可以支持，目前可以转为列表
            lines = []
            max_v = max((d.get('total_forwards', 0) for d in history), default=1)
            for d in history:
                count = d.get('total_forwards', 0)
                bar = "█" * int(count/max_v * 10)
                lines.append(f"`{d.get('date')[-5:]}`: {bar} {count}")
            builder.add_section("日写入量分布", lines)
            
        builder.add_button("刷新", "new_menu:db_performance_trends", icon="🔄")
        builder.add_button("返回", "new_menu:db_performance_monitor", icon="👈")
        return builder.build()

    def render_db_alert_management(self, data: Dict[str, Any]) -> ViewResult:
        """渲染告警管理页"""
        anomalies = data.get('anomalies', [])
        builder = self.new_builder()
        builder.set_title("数据库告警中心", icon="🚨")
        
        if anomalies:
            for a in anomalies:
                builder.add_section(f"[{a.get('severity').upper()}] {a.get('message')}", [], icon=a.get('icon', '⚠️'))
        else:
            builder.add_section("告警状态", "✅ 系统健康，无活跃告警记录。")
            
        builder.add_button("调整阈值", "new_menu:db_alert_config", icon="🔧")
        builder.add_button("清除历史", "new_menu:db_clear_alerts", icon="🗑️")
        builder.add_button("返回", "new_menu:db_performance_monitor", icon="👈")
        return builder.build()

    def render_db_optimization_advice(self, data: Dict[str, Any]) -> ViewResult:
        """渲染优化建议页"""
        builder = self.new_builder()
        builder.set_title("专家优化建议", icon="💡")
        builder.add_progress_bar("优化空间评分", data.get('health_score', 100))
        builder.add_section("建议执行操作", data.get('recommendations', ["所有参数已处于最优状态"]))
        builder.add_button("执行全量优化", "new_menu:enable_db_optimization", icon="🚀")
        builder.add_button("返回", "new_menu:db_performance_monitor", icon="👈")
        return builder.build()

    def render_db_detailed_report(self, data: Dict[str, Any]) -> ViewResult:
        """渲染详细报告页"""
        info = data.get('info', {})
        builder = self.new_builder()
        builder.set_title("数据库物理全息报告", icon="📋")
        builder.add_status_grid({
            "文件大小": f"{info.get('size_mb', 0):.2f} MB",
            "完整度": data.get('integrity', 'Pass'),
            "总记录数": f"{info.get('total_rows', 0)}"
        })
        tables = info.get('tables', {})
        if tables:
            lines = [f"• `{k}`: {v} 行" for k, v in tables.items()]
            builder.add_section("核心数据分布", lines)
        builder.add_button("返回", "new_menu:db_performance_monitor", icon="👈")
        return builder.build()

    def render_db_optimization_config(self, data: Dict[str, Any]) -> ViewResult:
        """渲染优化配置页"""
        config = data.get('config', {})
        return (self.new_builder()
            .set_title("底层优化配置", icon="⚙️")
            .add_status_grid({
                "Auto Vacuum": "ON" if config.get('auto_vacuum') else "OFF",
                "WAL Mode": "ENABLED" if config.get('wal_mode') else "DISABLED",
                "Sync Mode": config.get('sync_mode', 'NORMAL')
            })
            .add_section("安全提示", "修改底层存储模式可能需要重启全局服务。")
            .add_button("返回", "new_menu:db_optimization_center", icon=UIStatus.BACK)
            .build())

    def render_db_index_analysis(self, data: Dict[str, Any]) -> ViewResult:
        """渲染索引分析页"""
        return (self.new_builder()
            .set_title("索引拓扑分析", icon="🔍")
            .add_section("核心索引状态", [
                "idx_media_signature: 良好 (覆盖率 100%)",
                "idx_rule_log: 建议碎片整理 (< 5%)"
            ])
            .add_button("重建索引", "new_menu:run_db_reindex", icon="🛠️")
            .add_button("返回", "new_menu:db_optimization_center", icon=UIStatus.BACK)
            .build())

    def render_db_cache_management(self, data: Dict[str, Any]) -> ViewResult:
        """渲染缓存管理页"""
        stats = data.get('stats', {})
        return (self.new_builder()
            .set_title("内存缓存治理", icon="🗂️")
            .add_status_grid({
                "签名池": f"{stats.get('cached_signatures', 0)} 条",
                "哈希桶": f"{stats.get('cached_content_hashes', 0)} 条"
            })
            .add_button("清空全局缓存", "new_menu:dedup_clear_cache", icon="🗑️")
            .add_button("返回", "new_menu:db_optimization_center", icon=UIStatus.BACK)
            .build())

    def render_db_optimization_logs(self, data: Dict[str, Any]) -> ViewResult:
        """渲染优化日志页"""
        return (self.new_builder()
            .set_title("引擎优化流水", icon="📋")
            .add_section("近期操作日志", data.get('logs', ["今日无自动化异常日志"]))
            .add_button("返回", "new_menu:db_optimization_center", icon=UIStatus.BACK)
            .build())
