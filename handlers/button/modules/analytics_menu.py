"""
数据分析菜单模块
处理统计概览、详细分析、性能监控、异常检测及报告导出
"""
import logging
from datetime import datetime, timedelta
from telethon import Button
from ..base import BaseMenu
from services.analytics_service import analytics_service

logger = logging.getLogger(__name__)

class AnalyticsMenu(BaseMenu):
    """数据分析菜单"""

    async def show_forward_analytics(self, event):
        """显示转发分析面板"""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_stats = await analytics_service.get_daily_summary(today_str)
            if today_stats.get("total_forwards", 0) == 0:
                for i in range(1, 8):
                    d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                    stats = await analytics_service.get_daily_summary(d)
                    if stats.get("total_forwards", 0) > 0:
                        today_str, today_stats = d, stats
                        break

            yesterday = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_stats = await analytics_service.get_daily_summary(yesterday)
            total_today = today_stats.get("total_forwards", 0)
            total_yesterday = yesterday_stats.get("total_forwards", 0)
            
            trend_text = f"{'📈' if total_today > total_yesterday else '📉' if total_today < total_yesterday else '➡️'} {((total_today - total_yesterday) / total_yesterday * 100 if total_yesterday > 0 else 0):+.1f}%" if total_yesterday > 0 else "🆕 首日数据"
            if today_str != datetime.now().strftime("%Y-%m-%d"): trend_text += f" (数据日期: {today_str})"

            text = f"📊 **转发分析面板** - {today_str}\n\n"
            text += f"📈 **今日概览**\n总转发数: {total_today} {trend_text}\n数据大小: {today_stats.get('total_size_bytes', 0) / 1024 / 1024:.1f} MB\n媒体时长: {today_stats.get('total_duration_seconds', 0) // 60} 分钟\n\n"
            
            types = today_stats.get("types", {})
            if types:
                text += "🎯 **热门内容类型**\n"
                for msg_type, count in sorted(types.items(), key=lambda x: x[1], reverse=True)[:5]:
                    text += f"  {msg_type}: {count} ({(count/total_today*100 if total_today > 0 else 0):.1f}%)\n"
                text += "\n"

            health_score = await self._calculate_system_health(today_stats)
            health_emoji = "🟢" if health_score > 90 else "🟡" if health_score > 70 else "🔴"
            text += f"🏥 **系统健康度**: {health_emoji} {health_score:.1f}/100\n"

            buttons = [
                [Button.inline("📊 详细统计", "new_menu:detailed_analytics"), Button.inline("🚨 异常检测", "new_menu:anomaly_detection")],
                [Button.inline("📈 性能分析", "new_menu:performance_analysis"), Button.inline("🔍 失败分析", "new_menu:failure_analysis")],
                [Button.inline("⏱️ 实时监控", "new_menu:realtime_monitor"), Button.inline("📋 导出报告", "new_menu:export_report")],
                [Button.inline("🔄 刷新数据", "new_menu:forward_analytics"), Button.inline("👈 返回主菜单", "new_menu:main_menu")],
            ]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"显示转发分析失败: {e}")
            await event.answer("加载分析数据失败", alert=True)

    async def _calculate_system_health(self, stats: dict) -> float:
        score = 100.0
        total = stats.get("total_forwards", 0)
        if total == 0: score -= 30
        elif total > 1000: score += 10
        if len(stats.get("types", {})) > 5: score += 5
        elif len(stats.get("types", {})) < 2: score -= 10
        return max(0, min(100, score))

    async def show_detailed_analytics(self, event):
        """详细分析（最近7天）"""
        try:
            data = await analytics_service.get_detailed_analytics(days=7)
            text = "📈 详细分析（7天）\n\n"
            if data.get("daily_trends"):
                text += "【每日转发】\n"
                for d in data["daily_trends"]: text += f"- {d['date']}: {d['total']} 条, {d['size_mb']:.1f} MB\n"
                text += "\n"
            if data.get("type_distribution"):
                text += "【类型分布】\n"
                for t in data["type_distribution"][:8]: text += f"- {t['type']}: {t['count']} ({t['percentage']:.1f}%)\n"
            buttons = [[Button.inline("👈 返回分析", "new_menu:forward_analytics")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"详细分析显示失败: {e}")
            await event.answer("加载失败", alert=True)

    async def show_performance_analysis(self, event):
        """性能分析"""
        try:
            m = await analytics_service.get_performance_metrics()
            sr, pf, qs = m.get("system_resources", {}), m.get("performance", {}), m.get("queue_status", {})
            text = (
                "⚙️ 性能分析\n\n"
                f"CPU: {sr.get('cpu_percent', 0):.1f}%  内存: {sr.get('memory_percent', 0):.1f}%  状态: {sr.get('status', 'unknown')}\n"
                f"成功率: {pf.get('success_rate', 0):.1f}%  响应: {pf.get('avg_response_time', 0)}s  TPS: {pf.get('current_tps', 0)}\n"
                f"队列: {qs.get('active_queues', 'unknown')}  平均延迟: {qs.get('avg_delay', 'unknown')}  错误率: {qs.get('error_rate', 'unknown')}\n"
            )
            buttons = [[Button.inline("👈 返回分析", "new_menu:forward_analytics")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"性能分析失败: {e}")
            await event.answer("加载失败", alert=True)

    async def show_anomaly_detection(self, event):
        """显示异常检测结果"""
        try:
            today_stats = await analytics_service.get_daily_summary(datetime.now().strftime("%Y-%m-%d"))
            total = today_stats.get("total_forwards", 0)
            anomalies = []
            if total > 10000: anomalies.append("⚠️ 今日转发量异常偏高 (>10000)")
            elif total == 0: anomalies.append("🔴 今日无转发活动")
            
            text = "🚨 **异常检测报告**\n\n"
            if anomalies:
                text += "🔍 **发现的异常**\n" + "\n".join(anomalies) + "\n\n"
            else:
                text += "✅ **系统运行正常**\n无异常检测到\n\n"
            
            text += "💡 **建议操作**\n"
            if total > 5000: text += "• 考虑增加延迟防止频率限制\n"
            if not anomalies: text += "• 系统运行良好，继续保持\n"

            buttons = [[Button.inline("🔄 重新检测", "new_menu:anomaly_detection")], [Button.inline("👈 返回分析", "new_menu:forward_analytics")]]
            await self._render_from_text(event, text, buttons)
        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            await event.answer("异常检测失败", alert=True)

    async def export_report(self, event):
        """导出报告"""
        try:
            import os
            overview = await analytics_service.get_analytics_overview()
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"./reports/report_{now}.txt"
            os.makedirs("./reports", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"TelegramForwarder Report - {now}\nToday Total: {overview.get('overview',{}).get('today_total',0)}")
            await self._render_from_text(event, f"📤 报告已导出: {path}", [[Button.inline("👈 返回分析", "new_menu:forward_analytics")]])
        except Exception as e:
            logger.error(f"导出失败: {e}")
            await event.answer("导出失败", alert=True)

analytics_menu = AnalyticsMenu()
