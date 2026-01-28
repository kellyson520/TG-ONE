from typing import Dict, Any
from telethon.tl.custom import Button
from .base_renderer import BaseRenderer

class MainMenuRenderer(BaseRenderer):
    """主菜单渲染器"""
    
    def render(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        try:
            today_stats = stats.get('today', {})
            dedup_stats = stats.get('dedup', {})
            
            forwards = today_stats.get('total_forwards', 0)
            cached = dedup_stats.get('cached_signatures', 0)
            size_mb = today_stats.get('total_size_bytes', 0) / 1024 / 1024
            
            text = (
                "🌌 **Telegram 智能中枢**\n"
                "➖➖➖➖➖➖➖➖➖➖\n\n"
                
                "📊 **今日数据看板**\n"
                "├─ 📤 转发消息：`{forwards:,}` 条\n"
                "├─ 🧹 拦截重复：`{cached:,}` 次\n"
                "└─ 💾 节省流量：`{size_mb:.1f}` MB\n\n"
                
                "⚙️ **系统状态**\n"
                f"└─ 🟢 运行正常  |  ⏳ 延迟: 低\n\n"
                
                "👇 **请选择功能模块**"
            ).format(forwards=forwards, cached=cached, size_mb=size_mb)
            
            buttons = [
                [Button.inline("🔄 转发管理中心", "new_menu:forward_hub"),
                 Button.inline("🧹 智能去重中心", "new_menu:dedup_hub")],
                [Button.inline("📊 数据分析中心", "new_menu:analytics_hub"),
                 Button.inline("⚙️ 系统设置中心", "new_menu:system_hub")],
                [Button.inline("🔄 刷新数据", "new_menu:refresh_main_menu"),
                 Button.inline("📖 使用帮助", "new_menu:help_guide")],
                [Button.inline("🔒 退出系统", "new_menu:exit")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            return self.create_error_view("数据加载失败", "系统数据暂时不可用，请尝试刷新或稍后重试。", "new_menu:exit")

    def render_forward_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染转发管理中心"""
        overview = data.get('overview', {})
        text = (
            "🔄 **转发管理中心**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 **描述**\n"
            "全面管理您的转发规则、历史消息处理、筛选设置等功能。\n\n"
        )
        if overview:
            forwards = overview.get('total_forwards', 0)
            size_mb = overview.get('total_size_bytes', 0) / 1024 / 1024
            chats = overview.get('active_chats', 0)
            text += (
                "📊 **今日数据概览**\n"
                f"  📤 转发消息：**{forwards:,}** 条\n"
                f"  💾 数据传输：**{size_mb:.1f}** MB\n"
                f"  💬 活跃聊天：**{chats}** 个\n\n"
            )
        else:
            text += "📊 **今日数据概览** - 正在加载...\n\n"
        
        text += (
            "⚡ **快速操作中心**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        buttons = [
            [Button.inline("⚙️ 转发规则管理", "new_menu:forward_management"),
             Button.inline("📋 历史消息处理", "new_menu:history_messages")],
            [Button.inline("🔍 转发内容搜索", "new_menu:forward_search"),
             Button.inline("📊 详细统计分析", "new_menu:forward_stats_detailed")],
            [Button.inline("🎛️ 全局筛选设置", "new_menu:global_forward_settings"),
             Button.inline("🚀 性能监控优化", "new_menu:forward_performance")],
            [Button.inline("🔄 刷新数据", "new_menu:refresh_forward_hub"),
             Button.inline("🏠 返回主菜单", "new_menu:main_menu")]
        ]
        return {'text': text, 'buttons': buttons}

    def render_dedup_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染智能去重中心"""
        config = data.get('config', {})
        stats = data.get('stats', {})
        enabled_features = data.get('enabled_features', [])
        
        text = (
            "🧹 **智能去重中心**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 **描述**\n"
            "全面的重复内容检测和管理系统，保证转发内容的独特性。\n\n"
        )
        
        features_text = ", ".join(enabled_features) if enabled_features else "💫 暂无启用"
        time_window = config.get('time_window_hours', 24)
        similarity = config.get('similarity_threshold', 0.85)
        
        text += (
            "📊 **系统状态概览**\n"
            f"  ⚙️ 启用功能：{features_text}\n"
            f"  ⏰ 时间窗口：**{time_window}** 小时\n"
            f"  🎯 相似度阈值：**{similarity:.0%}**\n\n"
        )
        
        signatures = stats.get('cached_signatures', 0)
        hashes = stats.get('cached_content_hashes', 0)
        chats = stats.get('tracked_chats', 0)
        
        text += (
            "💾 **缓存数据统计**\n"
            f"  📝 内容签名：**{signatures:,}** 条\n"
            f"  🔐 哈希值：**{hashes:,}** 条\n"
            f"  💬 跟踪聊天：**{chats}** 个\n\n"
        )
        
        text += (
            "⚡ **功能管理中心**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        buttons = [
            [Button.inline("⏰ 时间窗口设置", "new_menu:dedup_time_window"),
             Button.inline("🎯 相似度调节", "new_menu:dedup_similarity")],
            [Button.inline("🔐 内容哈希管理", "new_menu:dedup_content_hash"),
             Button.inline("📊 数据统计分析", "new_menu:dedup_statistics")],
            [Button.inline("⚙️ 高级功能设置", "new_menu:dedup_advanced"),
             Button.inline("🗑️ 缓存数据清理", "new_menu:dedup_cache_management")],
            [Button.inline("🏠 返回主菜单", "new_menu:main_menu")]
        ]
        return {'text': text, 'buttons': buttons}

    def render_analytics_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染数据分析中心"""
        overview = data.get('overview', {})
        top_type = data.get('top_type')
        top_chat = data.get('top_chat')
        top_rule = data.get('top_rule')
        
        text = "📊 **数据分析中心**\n\n"
        text += "全面的数据统计、性能监控和异常检测。\n\n"
        
        if overview:
            trend = overview.get('trend', {})
            text += "📈 **转发趋势:**\n"
            text += f"今日: {overview.get('today_total', 0)} 条 {trend.get('text', '')}\n"
            text += f"昨日: {overview.get('yesterday_total', 0)} 条\n"
            text += f"数据大小: {overview.get('data_size_mb', 0):.1f} MB\n\n"
            
            if top_type:
                text += f"🎯 热门类型: {top_type['name']} ({top_type['count']} 条)\n"
            if top_chat:
                text += f"💬 活跃聊天: {top_chat['chat_id']} ({top_chat['count']} 条)\n"
            if top_rule:
                text += f"⚙️ 热门规则: {top_rule['rule_id']} ({top_rule['count']} 条)\n"

            hourly = overview.get('hourly', {}) or {}
            if hourly:
                try:
                    keys = [f"{h:02d}" for h in range(24)]
                    values = [hourly.get(k, 0) for k in keys]
                    max_v = max(values) if values else 0
                    if max_v > 0:
                        text += "\n🕒 小时分布\n"
                        for i in range(0, 24, 6):
                            seg_keys = keys[i:i+6]
                            seg_vals = values[i:i+6]
                            bar = ''.join('▇' if v and v / max_v > 0.66 else '▅' if v and v / max_v > 0.33 else '▂' if v and v > 0 else '·' for v in seg_vals)
                            text += f"{seg_keys[0]}-{seg_keys[-1]} {bar}\n"
                        text += "\n"
                except Exception:
                    pass
        else:
            text += "📈 **数据概览:** 正在加载...\n\n"
        
        text += "\n🔍 **分析工具:**"
        
        buttons = [
            [Button.inline("📊 转发分析", "new_menu:forward_analytics"),
             Button.inline("⏱️ 实时监控", "new_menu:realtime_monitor")],
            [Button.inline("🚨 异常检测", "new_menu:anomaly_detection"),
             Button.inline("📈 性能分析", "new_menu:performance_analysis")],
            [Button.inline("🗄️ 数据库监控", "new_menu:db_performance_monitor"),
             Button.inline("🔧 数据库优化", "new_menu:db_optimization_center")],
            [Button.inline("📋 详细报告", "new_menu:detailed_analytics"),
             Button.inline("📤 导出数据", "new_menu:export_report")],
            [Button.inline("🧾 导出CSV", "new_menu:export_csv")],
            [Button.inline("👈 返回主菜单", "new_menu:main_menu")]
        ]
        return {'text': text, 'buttons': buttons}

    def render_system_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染系统设置中心"""
        system_resources = data.get('system_resources', {})
        config_status = data.get('config_status', {})
        
        text = "⚙️ **系统设置中心**\n\n"
        text += "系统配置、会话管理和状态监控。\n\n"
        
        if system_resources:
            text += "🖥️ **系统状态:**\n"
            text += f"运行时间: {system_resources.get('uptime_hours', 0)} 小时\n"
            text += f"CPU使用: {system_resources.get('cpu_percent', 0):.1f}%\n"
            text += f"内存使用: {system_resources.get('memory_percent', 0):.1f}%\n\n"
        else:
            text += "🖥️ **系统状态:** 监控中...\n\n"
        
        text += "⚙️ **配置状态:**\n"
        text += f"• 转发规则: {config_status.get('forward_rules', '未知')}\n"
        text += f"• 智能去重: {config_status.get('smart_dedup', '未知')}\n"
        text += f"• 数据记录: {config_status.get('data_recording', '未知')}\n\n"
        
        text += "🛠️ **管理功能:**"
        
        buttons = [
            [Button.inline("⚙️ 基础设置", "new_menu:system_settings"),
             Button.inline("💬 会话管理", "new_menu:session_management")],
            [Button.inline("📋 系统概览", "new_menu:system_overview"),
             Button.inline("📊 系统状态", "new_menu:system_status")],
            [Button.inline("🔧 高级配置", "new_menu:system_settings"),
             Button.inline("🗑️ 数据清理", "new_menu:cache_cleanup")],
            [Button.inline("📚 日志查看", "new_menu:log_viewer"),
             Button.inline("🔄 重启服务", "new_menu:system_status")],
            [Button.inline("🧳 归档/优化一次", "new_menu:db_archive_once")],
            [Button.inline("🧨 强制归档（测试）", "new_menu:db_archive_force")],
            [Button.inline("🌸 重建Bloom索引", "new_menu:rebuild_bloom")],
            [Button.inline("👈 返回主菜单", "new_menu:main_menu")]
        ]
        return {'text': text, 'buttons': buttons}

    def render_help_guide(self) -> Dict[str, Any]:
        """渲染帮助说明页面"""
        text = "❓ **帮助说明**\n\n"
        text += "🎯 **四大功能模块介绍:**\n\n"
        
        text += "🔄 **转发管理**\n"
        text += "• 创建和管理转发规则\n"
        text += "• 批量处理历史消息\n"
        text += "• 全局转发设置\n"
        text += "• 性能优化配置\n\n"
        
        text += "🧹 **智能去重**\n"
        text += "• 时间窗口去重\n"
        text += "• 内容哈希比较\n"
        text += "• 智能相似度检测\n"
        text += "• 缓存管理\n\n"
        
        text += "📊 **数据分析**\n"
        text += "• 转发统计分析\n"
        text += "• 实时性能监控\n"
        text += "• 异常检测报告\n"
        text += "• 数据导出功能\n\n"
        
        text += "⚙️ **系统设置**\n"
        text += "• 基础系统配置\n"
        text += "• 会话管理\n"
        text += "• 系统状态监控\n"
        text += "• 日志管理\n\n"
        
        text += "💡 **使用建议:**\n"
        text += "1. 首次使用建议先配置转发规则\n"
        text += "2. 启用智能去重提高效率\n"
        text += "3. 定期查看数据分析了解使用情况\n"
        text += "4. 根据需要调整系统设置"
        
        buttons = [
            [Button.inline("📖 在线帮助文档", "new_menu:detailed_docs"),
             Button.inline("❓ 常见问题解答", "new_menu:faq")],
            [Button.inline("🛠️ 技术支持", "new_menu:tech_support"),
             Button.inline("ℹ️ 版本更新信息", "new_menu:version_info")],
            [Button.inline("🏠 返回主菜单", "new_menu:main_menu")]
        ]
        return {'text': text, 'buttons': buttons}
