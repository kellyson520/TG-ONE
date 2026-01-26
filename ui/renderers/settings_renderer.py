from typing import Dict, Any, List
from telethon.tl.custom import Button
from .base_renderer import BaseRenderer

class SettingsRenderer(BaseRenderer):
    """设置与分析渲染器"""
    
    def render_dedup_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染去重设置页面"""
        try:
            config = data.get('config', {})
            enabled = config.get('enable_time_window', True)
            hours = config.get('time_window_hours', 24)
            
            text = "⏰ **时间窗口去重设置**\n\n"
            text += "时间窗口去重会在指定时间内避免重复转发相同内容。\n\n"
            text += f"当前状态: {'✅ 启用' if enabled else '❌ 禁用'}\n"
            text += f"时间窗口: {'永久' if int(hours) <= 0 else str(hours)+' 小时'}\n\n"
            text += "💡 推荐设置:\n"
            text += "• 1小时: 适合高频转发\n"
            text += "• 24小时: 平衡设置(推荐)\n"
            text += "• 72小时: 严格去重\n"
            text += "• 168小时(7天): 最严格\n"
            
            buttons = [
                [Button.inline(f"{'🔴 关闭' if enabled else '🟢 开启'}", f"new_menu:toggle_time_window:{not enabled}")],
                [Button.inline("1时", "new_menu:set_time_window:1"),
                 Button.inline("6时", "new_menu:set_time_window:6"),
                 Button.inline("12时", "new_menu:set_time_window:12")],
                [Button.inline("24时⭐", "new_menu:set_time_window:24"),
                 Button.inline("72时", "new_menu:set_time_window:72"),
                  Button.inline("7天", "new_menu:set_time_window:168")],
                [Button.inline("♾ 永久", "new_menu:set_time_window:0")],
                [Button.inline("👈 返回去重设置", "new_menu:dedup_hub")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
            return self.create_error_view("设置加载失败", "错误", "new_menu:dedup_hub")

    def render_anomaly_detection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染异常检测页面"""
        try:
            anomalies = data.get('anomalies', [])
            recommendations = data.get('recommendations', [])
            health_score = data.get('health_score', 75.0)
            
            text = "🚨 **异常检测报告**\n\n"
            
            if anomalies:
                text += "🔍 **发现的异常**\n"
                for anomaly in anomalies:
                    text += f"{anomaly['icon']} {anomaly['message']}\n"
                text += "\n"
            else:
                text += "✅ **系统运行正常**\n无异常检测到\n\n"
            
            health_emoji = "🟢" if health_score > 90 else "🟡" if health_score > 70 else "🔴"
            text += f"🏥 **系统健康度**: {health_emoji} {health_score:.1f}/100\n\n"
            
            if recommendations:
                text += "💡 **建议操作**\n"
                for rec in recommendations:
                    text += f"• {rec}\n"
            else:
                text += "💡 **建议操作**\n• 系统运行良好，继续保持\n"
            
            buttons = [
                [Button.inline("🔄 重新检测", "new_menu:anomaly_detection")],
                [Button.inline("👈 返回分析", "new_menu:analytics_hub")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
            return self.create_error_view("检测加载失败", "错误", "new_menu:analytics_hub")

    def render_performance_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染性能监控页面"""
        try:
            system_resources = data.get('system_resources', {})
            performance = data.get('performance', {})
            queue_status = data.get('queue_status', {})
            
            text = "⏱️ **实时性能监控**\n\n"
            
            text += "🖥️ **系统资源**\n"
            cpu = system_resources.get('cpu_percent', 0)
            memory = system_resources.get('memory_percent', 0)
            
            text += f"CPU使用率: {cpu:.1f}%\n"
            text += f"内存使用率: {memory:.1f}%\n"
            text += f"系统状态: {self._get_status_icon(system_resources.get('status', 'unknown'))}\n\n"
            
            text += "📊 **性能指标**\n"
            success_rate = performance.get('success_rate', 0)
            response_time = performance.get('avg_response_time', 0)
            tps = performance.get('current_tps', 0)
            
            text += f"转发成功率: {success_rate:.1f}%\n"
            text += f"平均响应时间: {response_time:.2f}s\n"
            text += f"当前TPS: {tps:.1f}\n"
            text += f"性能状态: {self._get_status_icon(performance.get('status', 'unknown'))}\n\n"
            
            text += "📤 **队列状态**\n"
            text += f"队列状态: {queue_status.get('active_queues', '未知')}\n"
            text += f"平均延迟: {queue_status.get('avg_delay', '未知')}\n"
            text += f"错误率: {queue_status.get('error_rate', '未知')}\n"
            
            buttons = [
                [Button.inline("🔄 刷新数据", "new_menu:realtime_monitor"),
                 Button.inline("📈 详细报告", "new_menu:detailed_performance")],
                [Button.inline("⚙️ 性能调优", "new_menu:performance_tuning"),
                 Button.inline("👈 返回分析中心", "new_menu:analytics_hub")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
             return self.create_error_view("加载失败", "错误", "new_menu:analytics_hub")

    def render_db_performance_monitor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染数据库性能监控面板"""
        try:
            dashboard = data.get('dashboard', {})
            query_metrics = dashboard.get('query_metrics', {})
            system_metrics = dashboard.get('system_metrics', {})
            alerts = dashboard.get('alerts', [])
            
            text = "🗄️ **数据库性能监控**\n\n"
            text += "实时监控数据库性能指标、查询分析和系统告警。\n\n"
            
            if query_metrics:
                slow_queries = query_metrics.get('slow_queries', [])
                top_queries = query_metrics.get('top_queries', [])
                
                text += "🐌 **慢查询分析:**\n"
                if slow_queries:
                    text += f"当前慢查询: {len(slow_queries)} 个\n"
                    for sq in slow_queries[:3]:
                        duration = sq.get('duration', 0)
                        sql_preview = sq.get('sql', '')[:30] + '...' if len(sq.get('sql', '')) > 30 else sq.get('sql', '')
                        text += f"• {duration:.2f}s - {sql_preview}\n"
                else:
                    text += "✅ 暂无慢查询\n"
                text += "\n"
                
                text += "🔥 **热点查询:**\n"
                if top_queries:
                    for tq in top_queries[:3]:
                        count = tq.get('count', 0)
                        avg_time = tq.get('avg_time', 0)
                        sql_preview = tq.get('sql', '')[:25] + '...' if len(tq.get('sql', '')) > 25 else tq.get('sql', '')
                        text += f"• {count}次 ({avg_time:.3f}s) - {sql_preview}\n"
                else:
                    text += "📊 数据收集中...\n"
                text += "\n"
            
            if system_metrics:
                text += "💻 **系统指标:**\n"
                cpu_avg = system_metrics.get('cpu_usage', {}).get('avg', 0)
                memory_avg = system_metrics.get('memory_usage', {}).get('avg', 0)
                db_size = system_metrics.get('database_size', {}).get('current', 0)
                db_size_mb = db_size / (1024 * 1024) if db_size else 0
                
                text += f"CPU平均: {cpu_avg:.1f}%\n"
                text += f"内存平均: {memory_avg:.1f}%\n"
                text += f"数据库大小: {db_size_mb:.1f} MB\n"
                
                conn_stats = system_metrics.get('connection_count', {})
                if conn_stats:
                    text += f"连接数: 平均{conn_stats.get('avg', 0):.0f} 峰值{conn_stats.get('max', 0)}\n"
                text += "\n"
            
            if alerts:
                text += "🚨 **系统告警:**\n"
                for alert in alerts[:2]:
                    severity_icon = "🔴" if alert.get('severity') == 'critical' else "🟡"
                    text += f"{severity_icon} {alert.get('message', '未知告警')}\n"
                text += "\n"
            else:
                text += "✅ **系统状态:** 一切正常\n\n"
            
            text += "🔧 **监控工具:**"
            
            buttons = [
                [Button.inline("📊 查询分析", "new_menu:db_query_analysis"),
                 Button.inline("📈 性能趋势", "new_menu:db_performance_trends")],
                [Button.inline("🚨 告警管理", "new_menu:db_alert_management"),
                 Button.inline("⚙️ 优化建议", "new_menu:db_optimization_advice")],
                [Button.inline("🔄 刷新数据", "new_menu:db_performance_refresh"),
                 Button.inline("📋 详细报告", "new_menu:db_detailed_report")],
                [Button.inline("👈 返回分析中心", "new_menu:analytics_hub")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
            return self.create_error_view("加载失败", "错误", "new_menu:analytics_hub")
    
    def render_db_optimization_center(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染数据库优化中心"""
        try:
            status = data.get('status', {})
            recommendations = data.get('recommendations', [])
            components = status.get('components', {})
            
            text = "🔧 **数据库优化中心**\n\n"
            text += "智能优化系统，提升数据库性能和查询效率。\n\n"
            
            suite_status = status.get('suite_status', 'unknown')
            if suite_status == 'active':
                text += "✅ **优化系统:** 已启用\n\n"
            else:
                text += "❌ **优化系统:** 未启用\n\n"
            
            text += "📦 **组件状态:**\n"
            
            component_names = {
                'query_optimization': '查询优化',
                'monitoring': '性能监控',
                'sharding': '数据分片',
                'batch_processing': '批量处理'
            }
            
            for comp_key, comp_name in component_names.items():
                comp_status = components.get(comp_key, {}).get('status', 'unknown')
                status_icon = "✅" if comp_status == 'active' else "❌" if comp_status == 'error' else "🟡"
                text += f"{status_icon} {comp_name}: {comp_status}\n"
            
            text += "\n"
            
            if recommendations:
                text += "💡 **优化建议:**\n"
                for rec in recommendations[:3]:
                    priority = rec.get('priority', 'low')
                    priority_icon = "🔴" if priority == 'high' else "🟡" if priority == 'medium' else "🟢"
                    title = rec.get('title', '未知建议')
                    text += f"{priority_icon} {title}\n"
                text += "\n"
            else:
                text += "🎯 **状态:** 系统运行良好，暂无优化建议\n\n"
            
            text += "🛠️ **优化工具:**"
            
            buttons = [
                [Button.inline("🚀 启用优化", "new_menu:enable_db_optimization"),
                 Button.inline("📊 运行检查", "new_menu:run_db_optimization_check")],
                [Button.inline("📈 性能报告", "new_menu:db_performance_report"),
                 Button.inline("⚙️ 优化配置", "new_menu:db_optimization_config")],
                [Button.inline("🔍 索引分析", "new_menu:db_index_analysis"),
                 Button.inline("🗂️ 缓存管理", "new_menu:db_cache_management")],
                [Button.inline("🔄 刷新状态", "new_menu:db_optimization_refresh"),
                 Button.inline("📋 查看日志", "new_menu:db_optimization_logs")],
                [Button.inline("👈 返回分析中心", "new_menu:analytics_hub")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
             return self.create_error_view("加载失败", "错误", "new_menu:analytics_hub")

    def _get_status_icon(self, status: str) -> str:
        """获取状态图标"""
        status_icons = {
            'normal': '🟢 正常',
            'good': '🟢 良好',
            'warning': '🟡 警告',
            'high': '🟡 偏高',
            'critical': '🔴 严重',
            'poor': '🔴 较差',
            'error': '❌ 错误',
            'unknown': '❓ 未知'
        }
        return status_icons.get(status, f'❓ {status}')
