"""
菜单渲染器 - UI层
专门负责页面渲染，不包含业务逻辑
"""
from typing import Dict, List, Optional, Tuple, Any
from telethon.tl.custom import Button
import logging

logger = logging.getLogger(__name__)

class MenuRenderer:
    """菜单渲染器 - 纯UI渲染"""
    
    def render_main_menu(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """渲染主菜单"""
        try:
            today_stats = stats.get('today', {})
            dedup_stats = stats.get('dedup', {})
            
            # 美化统计数据显示
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
            logger.error(f"渲染主菜单失败: {e}")
            return {
                'text': (
                    "🚀 **Telegram 智能转发器**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "❌ **数据加载失败**\n"
                    "系统数据暂时不可用，请尝试刷新或稍后重试。\n\n"
                    "⚡ **功能中心** - 基础功能仍可使用\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                'buttons': [
                    [Button.inline("🔄 转发管理中心", "new_menu:forward_hub"),
                     Button.inline("🧹 智能去重中心", "new_menu:dedup_hub")],
                    [Button.inline("📊 数据分析中心", "new_menu:analytics_hub"),
                     Button.inline("⚙️ 系统设置中心", "new_menu:system_hub")],
                    [Button.inline("🔄 刷新数据", "new_menu:refresh_main_menu"),
                     Button.inline("🔒 退出系统", "new_menu:exit")]
                ]
            }
    
    def render_forward_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染转发管理中心"""
        try:
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
            
        except Exception as e:
            logger.error(f"渲染转发中心失败: {e}")
            return {
                'text': (
                    "🔄 **转发管理中心**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "❌ **错误** - 功能中心加载失败\n"
                    "请稍后重试或联系管理员。"
                ),
                'buttons': [[Button.inline("🏠 返回主菜单", "new_menu:main_menu")]]
            }
    
    def render_dedup_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染智能去重中心"""
        try:
            config = data.get('config', {})
            stats = data.get('stats', {})
            enabled_features = data.get('enabled_features', [])
            
            text = (
                "🧹 **智能去重中心**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "📝 **描述**\n"
                "全面的重复内容检测和管理系统，保证转发内容的独特性。\n\n"
            )
            
            # 优化状态显示
            features_text = ", ".join(enabled_features) if enabled_features else "💫 暂无启用"
            time_window = config.get('time_window_hours', 24)
            similarity = config.get('similarity_threshold', 0.85)
            
            text += (
                "📊 **系统状态概览**\n"
                f"  ⚙️ 启用功能：{features_text}\n"
                f"  ⏰ 时间窗口：**{time_window}** 小时\n"
                f"  🎯 相似度阈值：**{similarity:.0%}**\n\n"
            )
            
            # 优化缓存信息显示
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
            
        except Exception as e:
            logger.error(f"渲染去重中心失败: {e}")
            return {
                'text': (
                    "🧹 **智能去重中心**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "❌ **加载错误**\n"
                    "去重系统数据加载失败，请稍后重试。\n\n"
                    "🔧 **可能原因**\n"
                    "• 系统配置加载失败\n"
                    "• 数据库连接异常\n"
                    "• 缓存数据损坏"
                ),
                'buttons': [[Button.inline("🏠 返回主菜单", "new_menu:main_menu")]]
            }
    
    def render_analytics_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染数据分析中心"""
        try:
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

                # 小时分布（文本火柴图）
                hourly = overview.get('hourly', {}) or {}
                if hourly:
                    try:
                        keys = [f"{h:02d}" for h in range(24)]
                        values = [hourly.get(k, 0) for k in keys]
                        max_v = max(values) if values else 0
                        if max_v > 0:
                            text += "\n🕒 小时分布\n"
                            # 生成 12 段显示：每 2 小时合并
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
            
        except Exception as e:
            logger.error(f"渲染分析中心失败: {e}")
            return {
                'text': "📊 **数据分析中心**\n\n功能加载失败",
                'buttons': [[Button.inline("👈 返回主菜单", "new_menu:main_menu")]]
            }
    
    def render_system_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染系统设置中心"""
        try:
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
            
            # 配置状态
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
                # 方案A：将未实现的回调映射到已存在功能
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
            
        except Exception as e:
            logger.error(f"渲染系统中心失败: {e}")
            return {
                'text': "⚙️ **系统设置中心**\n\n功能加载失败",
                'buttons': [[Button.inline("👈 返回主菜单", "new_menu:main_menu")]]
            }
    
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
                [Button.inline(f"{'🔴 关闭' if enabled else '🟢 开启'}", 
                              f"new_menu:toggle_time_window:{not enabled}")],
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
            
        except Exception as e:
            logger.error(f"渲染去重设置失败: {e}")
            return {
                'text': "⏰ **时间窗口去重设置**\n\n设置加载失败",
                'buttons': [[Button.inline("👈 返回去重设置", "new_menu:dedup_hub")]]
            }
    
    def render_anomaly_detection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染异常检测页面"""
        try:
            anomalies = data.get('anomalies', [])
            recommendations = data.get('recommendations', [])
            health_score = data.get('health_score', 75.0)
            status = data.get('status', 'unknown')
            
            text = "🚨 **异常检测报告**\n\n"
            
            if anomalies:
                text += "🔍 **发现的异常**\n"
                for anomaly in anomalies:
                    text += f"{anomaly['icon']} {anomaly['message']}\n"
                text += "\n"
            else:
                text += "✅ **系统运行正常**\n无异常检测到\n\n"
            
            # 健康度显示
            health_emoji = "🟢" if health_score > 90 else "🟡" if health_score > 70 else "🔴"
            text += f"🏥 **系统健康度**: {health_emoji} {health_score:.1f}/100\n\n"
            
            # 建议操作
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
            
        except Exception as e:
            logger.error(f"渲染异常检测失败: {e}")
            return {
                'text': "🚨 **异常检测报告**\n\n检测功能加载失败",
                'buttons': [[Button.inline("👈 返回分析", "new_menu:analytics_hub")]]
            }
    
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
    
    def render_rule_list(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则列表页面"""
        try:
            rules = data.get('rules', [])
            pagination = data.get('pagination', {})
            
            text = (
                "⚙️ **转发规则管理**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            if not rules:
                text += (
                    "📭 **暂无转发规则**\n\n"
                    "💡 **开始使用**\n"
                    "点击下方 ➕ 新建规则 按钮创建您的第一个转发规则。\n\n"
                    "🔧 **功能说明**\n"
                    "• 支持关键词匹配\n"
                    "• 智能内容去重\n"
                    "• 灵活筛选规则\n"
                    "• 媒体文件转发\n"
                )
            else:
                total_count = pagination.get('total_count', 0)
                current_page = pagination.get('page', 0) + 1
                total_pages = pagination.get('total_pages', 1)
                page_size = pagination.get('page_size', 10)
                start_index = (current_page - 1) * page_size + 1
                end_index = min(current_page * page_size, total_count)
                
                text += f"📋 **规则列表概览** (共 {total_count:,} 条，当前第 {current_page}/{total_pages} 页，显示 {start_index}-{end_index} 条)\n\n"
                
                for i, rule in enumerate(rules, start_index):
                    source = rule.get('source_chat', {})
                    target = rule.get('target_chat', {})
                    
                    # 优化状态图标
                    status_icon = "🟢" if rule.get('enabled', True) else "🔴"
                    status_text = "运行中" if rule.get('enabled', True) else "已停用"
                    dedup_icon = "🧹 去重" if rule.get('enable_dedup', False) else "📝 普通"
                    
                    # 优化规则显示格式
                    source_name = source.get('title', 'Unknown')[:15]
                    target_name = target.get('title', 'Unknown')[:15]
                    if len(source.get('title', '')) > 15:
                        source_name += "..."
                    if len(target.get('title', '')) > 15:
                        target_name += "..."
                    
                    keywords_count = rule.get('keywords_count', 0)
                    replace_count = rule.get('replace_rules_count', 0)
                    
                    text += (
                        f"{status_icon} **规则 {rule['id']}** ({status_text})\n"
                        f"  📤 **源**：{source_name}\n"
                        f"  📥 **目标**：{target_name}\n"
                        f"  🏷️ **配置**：{keywords_count} 关键词 • {replace_count} 替换 • {dedup_icon}\n\n"
                    )
            
            # 优化分页信息显示
            current_page = pagination.get('page', 0) + 1
            total_pages = pagination.get('total_pages', 1)
            if total_pages > 1:
                text += (
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📄 **分页导航** 第 {current_page}/{total_pages} 页\n"
                )
            
            # 构建按钮
            buttons = []
            
            # 规则操作按钮
            if rules:
                rule_buttons = []
                for rule in rules[:10]:  # 最多显示10个规则按钮
                    rule_buttons.append(Button.inline(
                        f"📝 规则{rule['id']}", 
                        f"new_menu:edit_rule:{rule['id']}"
                    ))
                
                # 分组显示按钮，每行2个
                for i in range(0, len(rule_buttons), 2):
                    row = rule_buttons[i:i+2]
                    buttons.append(row)
            
            # 分页按钮
            page_buttons = []
            if pagination.get('has_prev', False):
                page_buttons.append(Button.inline("⬅️ 上页", f"new_menu:rule_list_page:{pagination.get('page', 0) - 1}"))
            else:
                page_buttons.append(Button.inline("⬅️ 上页", "noop"))  # 禁用状态
                
            if pagination.get('has_next', False):
                page_buttons.append(Button.inline("➡️ 下页", f"new_menu:rule_list_page:{pagination.get('page', 0) + 1}"))
            else:
                page_buttons.append(Button.inline("➡️ 下页", "noop"))  # 禁用状态
            
            buttons.append(page_buttons)
            
            # 优化管理按钮布局和文案
            buttons.extend([
                [Button.inline("➕ 创建新规则", "new_menu:create_rule"),
                 Button.inline("📊 统计分析", "new_menu:rule_statistics")],
                [Button.inline("🔗 批量管理", "new_menu:multi_source_management"),
                 Button.inline("🔍 搜索规则", "new_menu:search_rules")],
                [Button.inline("🎛️ 全局筛选设置", "new_menu:filter_settings"),
                 Button.inline("🔄 刷新数据", "new_menu:forward_management")],
                [Button.inline("🔙 返回转发中心", "new_menu:forward_hub")]
            ])
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            logger.error(f"渲染规则列表失败: {e}")
            return {
                'text': (
                    "⚙️ **转发规则管理**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "❌ **加载失败**\n"
                    "页面数据加载出现问题，请稍后重试。\n\n"
                    "💡 **可能原因**\n"
                    "• 网络连接问题\n"
                    "• 数据库暂时不可用\n"
                    "• 系统资源不足"
                ),
                'buttons': [[Button.inline("🔙 返回转发中心", "new_menu:forward_hub")]]
            }
    
    def render_rule_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则详情页面"""
        try:
            rule = data.get('rule', {})
            
            text = f"📋 **规则详情 - {rule.get('id', 'Unknown')}**\n\n"
            
            # 基本信息
            source = rule.get('source_chat', {})
            target = rule.get('target_chat', {})
            
            text += "📤 **源聊天**\n"
            text += f"   {source.get('title', 'Unknown')} ({source.get('telegram_chat_id', 'Unknown')})\n\n"
            
            text += "📥 **目标聊天**\n"
            text += f"   {target.get('title', 'Unknown')} ({target.get('telegram_chat_id', 'Unknown')})\n\n"
            
            # 规则设置
            settings = rule.get('settings', {})
            text += "⚙️ **规则设置**\n"
            text += f"   启用状态: {'✅ 已启用' if settings.get('enabled', True) else '❌ 已禁用'}\n"
            text += f"   智能去重: {'✅ 已启用' if settings.get('enable_dedup', False) else '❌ 已禁用'}\n"
            
            if settings.get('enable_dedup', False):
                text += f"   时间窗口: {settings.get('dedup_time_window_hours', 24)} 小时\n"
                text += f"   相似度阈值: {settings.get('similarity_threshold', 0.85):.0%}\n"
            
            text += "\n"
            
            # 关键词
            keywords = rule.get('keywords', [])
            text += f"🏷️ **关键词** ({len(keywords)} 个)\n"
            if keywords:
                for kw in keywords[:5]:  # 显示前5个
                    text += f"   • {kw}\n"
                if len(keywords) > 5:
                    text += f"   ... 还有 {len(keywords) - 5} 个\n"
            else:
                text += "   无关键词设置\n"
            text += "\n"
            
            # 替换规则
            replace_rules = rule.get('replace_rules', [])
            text += f"🔄 **替换规则** ({len(replace_rules)} 个)\n"
            if replace_rules:
                for rr in replace_rules[:3]:  # 显示前3个
                    text += f"   • {rr.get('pattern', '')} → {rr.get('replacement', '')}\n"
                if len(replace_rules) > 3:
                    text += f"   ... 还有 {len(replace_rules) - 3} 个\n"
            else:
                text += "   无替换规则设置\n"
            
            buttons = [
                [
                    Button.inline("🟢/🔴 切换状态", f"new_menu:toggle_rule:{rule.get('id')}"),
                    Button.inline("🗑️ 删除规则", f"new_menu:delete_rule_confirm:{rule.get('id')}")
                ],
                [
                    Button.inline("📝 基础转发设置", f"new_menu:rule_basic_settings:{rule.get('id')}"),
                    Button.inline("🎨 内容显示设置", f"new_menu:rule_display_settings:{rule.get('id')}")
                ],
                [
                    Button.inline("🚀 高级功能配置", f"new_menu:rule_advanced_settings:{rule.get('id')}"),
                    Button.inline("🎬 媒体过滤规则", f"media_settings:{rule.get('id')}")
                ],
                [
                    Button.inline("🤖 AI 增强处理", f"ai_settings:{rule.get('id')}"),
                    Button.inline("🔔 推送/同步设置", f"new_menu:rule_sync_push:{rule.get('id')}")
                ],
                [
                    Button.inline("🏷️ 管理关键词", f"new_menu:keywords:{rule.get('id')}"),
                    Button.inline("🔄 管理替换规则", f"new_menu:replaces:{rule.get('id')}")
                ],
                [Button.inline("👈 返回列表", "new_menu:list_rules:0")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            logger.error(f"渲染规则详情失败: {e}")
            return {
                'text': "📋 **规则详情**\n\n❌ 页面加载失败",
                'buttons': [[Button.inline("👈 返回列表", "new_menu:list_rules:0")]]
            }

    def render_rule_basic_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则基础转发设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        text = f"⚙️ **基础转发设置 - {rid}**\n\n"
        text += "配置转发的核心行为，如运行模式、转发身份等。\n\n"
        
        # 准备显示逻辑
        forward_mode_map = {
            'blacklist': '仅黑名单',
            'whitelist': '仅白名单',
            'blacklist_then_whitelist': '先黑后白',
            'whitelist_then_blacklist': '先白后黑'
        }
        
        buttons = [
            [Button.inline(f"运行状态: {'🟢 开启' if rule.get('enabled') else '🔴 禁用'}", f"new_menu:toggle_rule_set:{rid}:enabled")],
            [Button.inline(f"转发方式: {'🤖 机器人' if rule.get('use_bot') else '👤 个人账号'}", f"new_menu:toggle_rule_set:{rid}:use_bot")],
            [Button.inline(f"过滤模式: {forward_mode_map.get(rule.get('forward_mode'), rule.get('forward_mode'))}", f"new_menu:toggle_rule_set:{rid}:forward_mode")],
            [Button.inline(f"处理方式: {'✍️ 编辑' if rule.get('handle_mode') == 'edit' else '📤 转发'}", f"new_menu:toggle_rule_set:{rid}:handle_mode")],
            [Button.inline(f"删除原消息: {'✅ 是' if rule.get('is_delete_original') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:is_delete_original")],
            [Button.inline("👈 返回规则详情", f"new_menu:rule_detail:{rid}")]
        ]
        return {'text': text, 'buttons': buttons}

    def render_rule_display_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则内容显示设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        text = f"🎨 **内容显示设置 - {rid}**\n\n"
        text += "配置转发后消息的外观展示，如图标、链接、发送者信息等。\n\n"
        
        mode_val = rule.get('message_mode', 'MARKDOWN')
        if hasattr(mode_val, 'value'):
            mode_val = mode_val.value
        elif hasattr(mode_val, 'name'):
            mode_val = mode_val.name
        
        buttons = [
            [Button.inline(f"消息格式: {str(mode_val).upper()}", f"new_menu:toggle_rule_set:{rid}:message_mode")],
            [Button.inline(f"预览链接: {'✅ 开启' if rule.get('is_preview') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:is_preview")],
            [Button.inline(f"原始发送者: {'✅ 显示' if rule.get('is_original_sender') else '❌ 隐藏'}", f"new_menu:toggle_rule_set:{rid}:is_original_sender")],
            [Button.inline(f"发送时间: {'✅ 显示' if rule.get('is_original_time') else '❌ 隐藏'}", f"new_menu:toggle_rule_set:{rid}:is_original_time")],
            [Button.inline(f"原始链接: {'✅ 附带' if rule.get('is_original_link') else '❌ 不附带'}", f"new_menu:toggle_rule_set:{rid}:is_original_link")],
            [Button.inline(f"过滤发送者信息: {'✅ 是' if rule.get('is_filter_user_info') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:is_filter_user_info")],
            [Button.inline(f"显示评论按钮: {'✅ 是' if rule.get('enable_comment_button') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:enable_comment_button")],
            [Button.inline("👈 返回规则详情", f"new_menu:rule_detail:{rid}")]
        ]
        return {'text': text, 'buttons': buttons}

    def render_rule_advanced_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则高级功能设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        text = f"🚀 **高级功能配置 - {rid}**\n\n"
        text += "配置转发的流转逻辑，如去重、延迟、同步等高级控制。\n\n"
        
        buttons = [
            [Button.inline(f"智能去重: {'✅ 开启' if rule.get('enable_dedup') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:enable_dedup")],
            [Button.inline(f"延迟处理: {'✅ 开启' if rule.get('enable_delay') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:enable_delay")],
            [Button.inline(f"延迟时间: {rule.get('delay_seconds', 0)} 秒", f"new_menu:set_rule_val:{rid}:delay_seconds")],
            [Button.inline(f"强制纯转发: {'✅ 是' if rule.get('force_pure_forward') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:force_pure_forward")],
            [Button.inline(f"规则快速同步: {'✅ 开启' if rule.get('enable_sync') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:enable_sync")],
            [Button.inline("👈 返回规则详情", f"new_menu:rule_detail:{rid}")]
        ]
        return {'text': text, 'buttons': buttons}
    
    def render_rule_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则统计页面"""
        try:
            stats = data.get('statistics', {})
            
            text = "📊 **转发规则统计**\n\n"
            
            total = stats.get('total_rules', 0)
            enabled = stats.get('enabled_rules', 0)
            disabled = stats.get('disabled_rules', 0)
            dedup_enabled = stats.get('dedup_enabled_rules', 0)
            percentage = stats.get('enabled_percentage', 0)
            
            text += "📈 **总体统计**\n"
            text += f"总规则数: {total} 条\n"
            text += f"已启用: {enabled} 条 ({percentage:.1f}%)\n"
            text += f"已禁用: {disabled} 条\n"
            text += f"启用去重: {dedup_enabled} 条\n\n"
            
            # 可视化进度条
            if total > 0:
                enabled_bars = int(enabled / total * 10)
                disabled_bars = 10 - enabled_bars
                
                text += "📊 **启用状态分布**\n"
                text += f"{'🟢' * enabled_bars}{'⚪' * disabled_bars}\n"
                text += f"启用: {enabled_bars}/10 • 禁用: {disabled_bars}/10\n\n"
            
            # 去重统计
            if total > 0:
                dedup_percentage = (dedup_enabled / total) * 100
                text += "🧹 **去重功能使用率**\n"
                text += f"{dedup_percentage:.1f}% 的规则启用了智能去重\n"
            
            buttons = [
                [Button.inline("📋 查看规则列表", "new_menu:forward_management"),
                 Button.inline("➕ 创建新规则", "new_menu:create_rule")],
                [Button.inline("🔄 刷新统计", "new_menu:rule_statistics"),
                 Button.inline("👈 返回转发中心", "new_menu:forward_hub")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            logger.error(f"渲染规则统计失败: {e}")
            return {
                'text': "📊 **转发规则统计**\n\n❌ 统计加载失败",
                'buttons': [[Button.inline("👈 返回转发中心", "new_menu:forward_hub")]]
            }

    def render_manage_keywords(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染管理关键词页面（基础版）"""
        try:
            rule_id = data.get('rule_id')
            keywords = data.get('keywords', [])  # [{index,text,is_regex,is_blacklist}]
            text = f"🏷️ **管理关键词**\n\n规则: {rule_id}\n"
            text += f"当前共有 {len(keywords)} 个关键词\n\n"
            if keywords:
                for item in keywords:
                    tag = '(正则)' if item.get('is_regex') else ''
                    mode = '黑' if item.get('is_blacklist', True) else '白'
                    text += f"{item.get('index')}. [{mode}]{tag} {item.get('text','')}\n"
            else:
                text += "暂无关键词\n"

            buttons = [
                [Button.inline("➕ 添加关键词", f"new_menu:kw_add:{rule_id}")],
                [Button.inline("🗑️ 删除关键词", f"new_menu:kw_delete:{rule_id}")],
                [Button.inline("👈 返回规则详情", f"new_menu:edit_rule_settings:{rule_id}")]
            ]
            return {'text': text, 'buttons': buttons}
        except Exception as e:
            logger.error(f"渲染管理关键词失败: {e}")
            return {
                'text': "🏷️ **管理关键词**\n\n❌ 页面加载失败",
                'buttons': [[Button.inline("👈 返回规则列表", "new_menu:forward_management")]]
            }

    def render_manage_replace_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染管理替换规则页面（基础版）"""
        try:
            rule_id = data.get('rule_id')
            replace_rules = data.get('replace_rules', [])  # [{index,pattern,replacement}]
            text = f"🔄 **管理替换规则**\n\n规则: {rule_id}\n"
            text += f"当前共有 {len(replace_rules)} 条替换规则\n\n"
            if replace_rules:
                for rr in replace_rules:
                    pattern = rr.get('pattern', '')
                    replacement = rr.get('replacement', '')
                    text += f"{rr.get('index')}. {pattern} → {replacement}\n"
            else:
                text += "暂无替换规则\n"

            buttons = [
                [Button.inline("➕ 新增替换规则", f"new_menu:rr_add:{rule_id}")],
                [Button.inline("🗑️ 删除替换规则", f"new_menu:rr_delete:{rule_id}")],
                [Button.inline("👈 返回规则详情", f"new_menu:edit_rule_settings:{rule_id}")]
            ]
            return {'text': text, 'buttons': buttons}
        except Exception as e:
            logger.error(f"渲染管理替换规则失败: {e}")
            return {
                'text': "🔄 **管理替换规则**\n\n❌ 页面加载失败",
                'buttons': [[Button.inline("👈 返回规则列表", "new_menu:forward_management")]]
            }
    
    def render_performance_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染性能监控页面"""
        try:
            system_resources = data.get('system_resources', {})
            performance = data.get('performance', {})
            queue_status = data.get('queue_status', {})
            
            text = "⏱️ **实时性能监控**\n\n"
            
            # 系统资源
            text += "🖥️ **系统资源**\n"
            cpu = system_resources.get('cpu_percent', 0)
            memory = system_resources.get('memory_percent', 0)
            
            text += f"CPU使用率: {cpu:.1f}%\n"
            text += f"内存使用率: {memory:.1f}%\n"
            text += f"系统状态: {self._get_status_icon(system_resources.get('status', 'unknown'))}\n\n"
            
            # 性能指标
            text += "📊 **性能指标**\n"
            success_rate = performance.get('success_rate', 0)
            response_time = performance.get('avg_response_time', 0)
            tps = performance.get('current_tps', 0)
            
            text += f"转发成功率: {success_rate:.1f}%\n"
            text += f"平均响应时间: {response_time:.2f}s\n"
            text += f"当前TPS: {tps:.1f}\n"
            text += f"性能状态: {self._get_status_icon(performance.get('status', 'unknown'))}\n\n"
            
            # 队列状态
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
            
        except Exception as e:
            logger.error(f"渲染性能监控失败: {e}")
            return {
                'text': "⏱️ **实时性能监控**\n\n❌ 监控数据加载失败",
                'buttons': [[Button.inline("👈 返回分析中心", "new_menu:analytics_hub")]]
            }
    
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
    
    def _render_progress_bar(self, percentage: float, length: int = 15) -> str:
        """渲染平滑的Unicode进度条"""
        # 使用更细腻的Unicode块
        blocks = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
        full_blocks = int(percentage / 100 * length)
        remainder = (percentage / 100 * length) - full_blocks
        remainder_idx = int(remainder * 8)
        
        bar = "█" * full_blocks
        if full_blocks < length:
            bar += blocks[remainder_idx]
            bar += "░" * (length - full_blocks - 1)
        return f"`{bar}`"
    
    def render_history_task_selector(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染历史任务规则选择页面"""
        try:
            rules = data.get('rules', [])
            current_selection = data.get('current_selection', {})
            # 历史去重开关（来自当前选择或默认 False）
            dedup_enabled = False
            try:
                dedup_enabled = bool(current_selection.get('dedup_enabled', False))
            except Exception:
                dedup_enabled = False
            
            text = "📝 **选择历史消息任务规则**\n\n"
            text += "💡 **操作提示**: 选择规则后进入操作页面进行设置\n\n"
            
            if not rules:
                text += "❌ **暂无可用规则**\n"
                text += "请先创建并启用至少一个转发规则。\n\n"
                buttons = [
                    [Button.inline("➕ 创建规则", "new_menu:create_rule")],
                    [Button.inline("👈 返回转发中心", "new_menu:forward_hub")]
                ]
                return {'text': text, 'buttons': buttons}
            
            # 显示当前选择（兼容不同字段名：title/name/telegram_chat_id）
            if current_selection.get('has_selection'):
                rule = current_selection.get('rule', {})
                def _chat_text(chat: Dict[str, Any]) -> str:
                    if not isinstance(chat, dict):
                        return 'Unknown'
                    return (
                        str(chat.get('title'))
                        or str(chat.get('name'))
                        or str(chat.get('telegram_chat_id') or 'Unknown')
                    )
                text += f"✅ **当前选择**: 规则 {current_selection.get('rule_id')}\n"
                text += f"   📤 {_chat_text(rule.get('source_chat', {}))}\n"
                text += f"   📥 {_chat_text(rule.get('target_chat', {}))}\n\n"
            else:
                text += "⚪ **尚未选择规则**\n\n"
            
            text += f"📋 **可用规则** ({len(rules)} 个)\n\n"
            
            # 显示规则列表
            buttons = []
            for i, rule in enumerate(rules[:8], 1):  # 最多显示8个规则
                dedup_icon = "🧹" if rule.get('enable_dedup', False) else ""
                keywords_info = f"({rule.get('keywords_count', 0)} 关键词)" if rule.get('keywords_count', 0) > 0 else ""
                
                rule_text = f"{i}. {rule['source_title']} → {rule['target_title']} {dedup_icon}"
                if len(rule_text) > 25:
                    rule_text = rule_text[:22] + "..."
                
                buttons.append([Button.inline(
                    rule_text,
                    f"new_menu:select_history_rule:{rule['id']}"
                )])
            
            # 如果有更多规则，显示查看更多按钮
            if len(rules) > 8:
                buttons.append([Button.inline(f"📋 查看全部 {len(rules)} 个规则", "new_menu:view_all_rules")])
            
            # 只保留返回按钮，所有操作都在选择规则后的次级页面进行
            buttons.extend([
                [Button.inline("👈 返回转发中心", "new_menu:forward_hub")]
            ])
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            logger.error(f"渲染历史任务选择失败: {e}")
            return {
                'text': "📝 **选择历史消息任务规则**\n\n❌ 页面加载失败",
                'buttons': [[Button.inline("👈 返回转发中心", "new_menu:forward_hub")]]
            }
    
    def render_current_history_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染当前历史任务状态页面"""
        try:
            if not data.get('has_task', False):
                text = "📋 **历史消息任务**\n\n"
                text += "💤 **当前无运行任务**\n"
                text += "点击下方按钮开始新的历史消息转发任务。\n"
                
                buttons = [
                    [Button.inline("🚀 开始新任务", "new_menu:history_task_selector")],
                    [Button.inline("👈 返回转发中心", "new_menu:forward_hub")]
                ]
                
                return {'text': text, 'buttons': buttons}
            
            # 有运行中的任务
            status = data.get('status', 'unknown')
            progress = data.get('progress', {})
            
            text = "📋 **历史消息任务状态**\n\n"
            
            # 状态显示
            status_icons = {
                'running': '🟢 运行中',
                'completed': '✅ 已完成',
                'failed': '❌ 失败',
                'cancelled': '⏹️ 已取消'
            }
            text += f"状态: {status_icons.get(status, f'❓ {status}')}\n\n"
            
            # 进度信息
            if progress:
                total = progress.get('total', 0)
                done = progress.get('done', 0)
                forwarded = progress.get('forwarded', 0)
                filtered = progress.get('filtered', 0)
                failed = progress.get('failed', 0)
                percentage = progress.get('percentage', 0)
                
                text += "📊 **进度统计**\n"
                text += f"总计: {total} 条\n"
                text += f"已处理: {done} 条 ({percentage:.1f}%)\n"
                text += f"已转发: {forwarded} 条\n"
                text += f"已过滤: {filtered} 条\n"
                if failed > 0:
                    text += f"失败: {failed} 条\n"
                
                # 进度条
                if total > 0:
                    text += f"\n📈 {self._render_progress_bar(percentage)} **{percentage:.1f}%**\n"
                
                # 预估剩余时间
                estimated = data.get('estimated_remaining')
                if estimated and status == 'running':
                    text += f"\n⏱️ 预估剩余: {estimated}\n"
            
            # 操作按钮
            buttons = []
            if status == 'running':
                buttons.extend([
                    [Button.inline("🔄 刷新状态", "new_menu:current_history_task"),
                     Button.inline("⏹️ 取消任务", "new_menu:cancel_history_task")]
                ])
            else:
                buttons.extend([
                    [Button.inline("🚀 开始新任务", "new_menu:history_task_selector"),
                     Button.inline("📊 查看详情", "new_menu:history_task_details")]
                ])
            
            buttons.append([Button.inline("👈 返回转发中心", "new_menu:forward_hub")])
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            logger.error(f"渲染历史任务状态失败: {e}")
            return {
                'text': "📋 **历史消息任务状态**\n\n❌ 状态加载失败",
                'buttons': [[Button.inline("👈 返回转发中心", "new_menu:forward_hub")]]
            }
    
    def render_time_range_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染时间范围设置页面"""
        try:
            time_range = data.get('time_range', {})
            is_all_messages = data.get('is_all_messages', True)
            display_text = data.get('display_text', '全部时间')
            
            text = "⏰ **时间范围设置**\n\n"
            text += f"当前设置: {display_text}\n\n"
            
            if is_all_messages:
                text += "📅 **当前模式**: 获取全部消息\n"
                text += "这将处理聊天中的所有历史消息，可能需要较长时间。\n\n"
            else:
                text += "📅 **当前模式**: 自定义时间范围\n"
                text += "仅处理指定时间范围内的消息。\n\n"
            
            text += "🎯 **快速设置**:"
            
            buttons = [
                [Button.inline("🌟 全部消息", "new_menu:set_time_range_all"),
                 Button.inline("📅 最近7天", "new_menu:set_time_range_days:7")],
                [Button.inline("📆 最近30天", "new_menu:set_time_range_days:30"),
                 Button.inline("📊 最近90天", "new_menu:set_time_range_days:90")],
                [Button.inline("🕐 自定义开始时间", "new_menu:set_start_time"),
                 Button.inline("🕕 自定义结束时间", "new_menu:set_end_time")],
                [Button.inline("✅ 确认设置", "new_menu:confirm_time_range"),
                 Button.inline("👈 返回任务设置", "new_menu:history_task_actions")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            logger.error(f"渲染时间范围设置失败: {e}")
            return {
                'text': "⏰ **时间范围设置**\n\n❌ 设置加载失败",
                'buttons': [[Button.inline("👈 返回任务设置", "new_menu:history_task_actions")]]
            }

    def render_history_task_actions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染历史任务的操作子菜单（选择任务后的下级菜单）"""
        try:
            selected = data.get('selected', {}) or {}
            has_sel = selected.get('has_selection', False)
            rid = selected.get('rule_id') if has_sel else None
            dedup_enabled = data.get('dedup_enabled', False)
            title = "🧭 **历史任务 - 操作**\n\n"
            if has_sel:
                title += f"当前规则: {rid}\n\n"
            else:
                title += "未选择规则\n\n"
            buttons = [
                [Button.inline("⚙️ 时间范围", "new_menu:history_time_range")],
                [Button.inline("⏱️ 延迟设置", "new_menu:history_delay_settings")],
                [Button.inline(f"🧹 历史去重：{'开启' if dedup_enabled else '关闭'}", "new_menu:toggle_history_dedup")],
                [Button.inline("📊 快速统计(服务端)", "new_menu:history_quick_stats")],
                [Button.inline("🧪 干跑(不发送)", "new_menu:history_dry_run")],
                [Button.inline("🗑️ 清理任务状态", "new_menu:cleanup_history_tasks")],
                [Button.inline("🚀 开始任务", "new_menu:start_history_task")],
                [Button.inline("👈 返回任务选择", "new_menu:history_task_selector")]
            ]
            return {'text': title, 'buttons': buttons}
        except Exception as e:
            logger.error(f"渲染历史任务操作子菜单失败: {e}")
            return {
                'text': "🧭 **历史任务 - 操作**\n\n❌ 页面加载失败",
                'buttons': [[Button.inline("👈 返回任务选择", "new_menu:history_task_selector")]]
            }
    
    def render_delay_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染延迟设置页面"""
        try:
            delay_seconds = data.get('delay_seconds', 1)
            delay_text = data.get('delay_text', '1秒')
            
            text = "⏱️ **转发延迟设置**\n\n"
            text += f"当前延迟: {delay_text}\n\n"
            text += "🛡️ **延迟作用**:\n"
            text += "• 防止触发Telegram频率限制\n"
            text += "• 避免账号被限制或封禁\n"
            text += "• 提高转发成功率\n\n"
            text += "💡 **推荐设置**:\n"
            text += "• 测试环境: 无延迟或1秒\n"
            text += "• 正常使用: 1-3秒\n"
            text += "• 大量转发: 5-10秒\n"
            text += "• 敏感账号: 10秒以上\n"
            
            buttons = [
                [Button.inline("⚡ 无延迟", "new_menu:set_delay:0"),
                 Button.inline("🚀 1秒", "new_menu:set_delay:1"),
                 Button.inline("⭐ 3秒", "new_menu:set_delay:3")],
                [Button.inline("🛡️ 5秒", "new_menu:set_delay:5"),
                 Button.inline("🔒 10秒", "new_menu:set_delay:10"),
                 Button.inline("🐌 30秒", "new_menu:set_delay:30")],
                [Button.inline("🎛️ 自定义", "new_menu:custom_delay"),
                 Button.inline("👈 返回任务设置", "new_menu:history_task_actions")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            logger.error(f"渲染延迟设置失败: {e}")
            return {
                'text': "⏱️ **转发延迟设置**\n\n❌ 设置加载失败",
                'buttons': [[Button.inline("👈 返回任务设置", "new_menu:history_task_actions")]]
            }
    
    def render_db_performance_monitor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染数据库性能监控面板"""
        try:
            dashboard = data.get('dashboard', {})
            query_metrics = dashboard.get('query_metrics', {})
            system_metrics = dashboard.get('system_metrics', {})
            alerts = dashboard.get('alerts', [])
            
            text = "🗄️ **数据库性能监控**\n\n"
            text += "实时监控数据库性能指标、查询分析和系统告警。\n\n"
            
            # 慢查询统计
            if query_metrics:
                slow_queries = query_metrics.get('slow_queries', [])
                top_queries = query_metrics.get('top_queries', [])
                
                text += "🐌 **慢查询分析:**\n"
                if slow_queries:
                    text += f"当前慢查询: {len(slow_queries)} 个\n"
                    for sq in slow_queries[:3]:  # 显示前3个
                        duration = sq.get('duration', 0)
                        sql_preview = sq.get('sql', '')[:30] + '...' if len(sq.get('sql', '')) > 30 else sq.get('sql', '')
                        text += f"• {duration:.2f}s - {sql_preview}\n"
                else:
                    text += "✅ 暂无慢查询\n"
                text += "\n"
                
                # 热点查询
                text += "🔥 **热点查询:**\n"
                if top_queries:
                    for tq in top_queries[:3]:  # 显示前3个
                        count = tq.get('count', 0)
                        avg_time = tq.get('avg_time', 0)
                        sql_preview = tq.get('sql', '')[:25] + '...' if len(tq.get('sql', '')) > 25 else tq.get('sql', '')
                        text += f"• {count}次 ({avg_time:.3f}s) - {sql_preview}\n"
                else:
                    text += "📊 数据收集中...\n"
                text += "\n"
            
            # 系统指标
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
            
            # 告警信息
            if alerts:
                text += "🚨 **系统告警:**\n"
                for alert in alerts[:2]:  # 显示前2个告警
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
            
        except Exception as e:
            logger.error(f"渲染数据库监控面板失败: {e}")
            return {
                'text': "🗄️ **数据库性能监控**\n\n❌ 监控面板加载失败",
                'buttons': [[Button.inline("👈 返回分析中心", "new_menu:analytics_hub")]]
            }
    
    def render_db_optimization_center(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染数据库优化中心"""
        try:
            status = data.get('status', {})
            recommendations = data.get('recommendations', [])
            components = status.get('components', {})
            
            text = "🔧 **数据库优化中心**\n\n"
            text += "智能优化系统，提升数据库性能和查询效率。\n\n"
            
            # 优化系统状态
            suite_status = status.get('suite_status', 'unknown')
            if suite_status == 'active':
                text += "✅ **优化系统:** 已启用\n\n"
            else:
                text += "❌ **优化系统:** 未启用\n\n"
            
            # 组件状态
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
            
            # 优化建议
            if recommendations:
                text += "💡 **优化建议:**\n"
                for rec in recommendations[:3]:  # 显示前3个建议
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
            
        except Exception as e:
            logger.error(f"渲染数据库优化中心失败: {e}")
            return {
                'text': "🔧 **数据库优化中心**\n\n❌ 优化中心加载失败",
                'buttons': [[Button.inline("👈 返回分析中心", "new_menu:analytics_hub")]]
            }

# 全局渲染器实例
menu_renderer = MenuRenderer()
