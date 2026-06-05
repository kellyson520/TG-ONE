import logging
import traceback
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union

from services.network.bot_heartbeat import get_heartbeat
from services.dedup.engine import smart_deduplicator
from core.helpers.realtime_stats import realtime_stats_cache

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    数据分析服务
    负责聚合来自各个 Repository 和工具类的统计信息
    """
    
    def __init__(self, container=None):
        self._container = container
        from core.archive.bridge import UnifiedQueryBridge
        self.bridge = UnifiedQueryBridge()

    @property
    def container(self):
        if self._container:
            return self._container
        from core.container import container
        return container

    def _get_dir_size(self, path: Path) -> int:
        """递归获取目录大小 (Bytes)"""
        total = 0
        try:
            if not path.exists():
                return 0
            for entry in os.scandir(path):
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += self._get_dir_size(Path(entry.path))
        except Exception as e:
            logger.debug(f"计算目录大小时跳过 {path}: {e}")
        return total

    async def get_data_size_mb(self) -> float:
        """获取数据目录总大小 (MB)"""
        try:
            from core.config import settings
            # 统一使用 DATA_ROOT
            data_root = Path(settings.DATA_ROOT)
            total_bytes = self._get_dir_size(data_root)
            return round(total_bytes / (1024 * 1024), 2)
        except Exception as e:
            logger.error(f"获取数据目录大小失败: {e}")
            return 0.0

    async def get_analytics_overview(self) -> Dict[str, Any]:
        """获取系统统计总览"""
        try:
            # 1. 获取规则统计
            rule_stats = await self.container.task_repo.get_rule_stats()
            overview = {
                'total_rules': rule_stats.get('total_rules', 0),
                'active_rules': rule_stats.get('active_rules', 0),
                'total_chats': rule_stats.get('total_chats', 0)
            }
            
            # 2. 获取转发统计 (从缓存获取以对齐 Bot 菜单)
            forward_stats = {'total_forwards': 0}
            try:
                from core.helpers.realtime_stats import realtime_stats_cache
                fs = await realtime_stats_cache.get_forward_stats()
                if isinstance(fs, dict):
                    ft = int(((fs.get('today') or {}).get('total_forwards') or 0))
                    if ft >= 0:
                        forward_stats = {'total_forwards': ft}
            except Exception as e:
                logger.warning(f"AnalyticsService 获取转发统计失败: {e}")
            
            # 3. 获取去重统计
            dedup_stats = {'cached_signatures': 0}
            try:
                dedup = smart_deduplicator.get_stats()
                dedup_stats = {'cached_signatures': int(dedup.get('cached_signatures', 0))}
            except Exception as e:
                logger.error(f"AnalyticsService 获取去重统计失败: {e}")
                
            # 4. 获取 HLL 独立消息估计
            hll_stats = {'unique_messages_estimate': 0}
            try:
                from core.algorithms.hll import GlobalHLL
                hll = GlobalHLL.get_hll("unique_messages_today")
                hll_stats = {'unique_messages_estimate': hll.count()}
            except Exception as e:
                logger.warning(f"AnalyticsService 获取 HLL 统计失败: {e}")

            # 5. 组合最终数据以对齐 Renderer 需求
            # 获取活跃分析数据(可能需要从 get_detailed_stats 组合部分)
            detailed = await self.get_detailed_stats(days=1)
            
            # 获取昨日统计
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_summary = await self.get_daily_summary(yesterday_str)
            yesterday_total = yesterday_summary.get('total_forwards', 0)
            
            # 强化 overview 字段以对齐 main_menu_renderer.py:140
            system_status = await self.get_system_status()
            enriched_overview = {
                'total_rules': overview.get('total_rules', 0),
                'active_rules': overview.get('active_rules', 0),
                'total_chats': overview.get('total_chats', 0),
                'today_total': forward_stats.get('total_forwards', 0),
                'yesterday_total': yesterday_total,
                'data_size_mb': system_status.get('system_resources', {}).get('total_size_mb', 0.0),
                'saved_traffic_bytes': (fs.get('today') or {}).get('saved_traffic_bytes', 0) if isinstance(fs, dict) else 0,
                'trend': {
                    'text': '📈 稳步增长' if forward_stats.get('total_forwards', 0) > yesterday_total else '⏸️ 待机中',
                    'percentage': round((forward_stats.get('total_forwards', 0) - yesterday_total) / yesterday_total * 100, 1) if yesterday_total > 0 else 0
                },
                'hourly': [{'hour': k, 'count': v} for k, v in detailed.get('time_analysis', {}).get('hourly_today', {}).items()]
            }

            return {
                'overview': enriched_overview,
                'forward_stats': forward_stats,
                'dedup_stats': dedup_stats,
                'hll_stats': hll_stats,
                'top_type': next(iter(detailed.get('type_distribution', [])), None),
                'top_chat': next(iter(detailed.get('top_chats', [])), None),
                'top_rule': next(iter(detailed.get('top_rules', [])), None)
            }
        except Exception as e:
            logger.error(f"get_analytics_overview 失败: {e}\n{traceback.format_exc()}")
            return {
                'overview': {'total_rules': 0, 'active_rules': 0, 'total_chats': 0},
                'forward_stats': {'total_forwards': 0},
                'dedup_stats': {'cached_signatures': 0},
                'error': str(e)
            }

    async def get_system_status(self) -> Dict[str, Any]:
        """获取各项服务运行状态 (为系统中心页面提供真实数据)"""
        try:
            # 1. 基础资源状态 (CPU/MEM/Uptime)
            import psutil
            import time
            from datetime import datetime
            
            # 运行时间
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime_hours = (datetime.now() - boot_time).total_seconds() / 3600
            
            # 数据大小
            total_size_mb = await self.get_data_size_mb()
            
            system_resources = {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "uptime_hours": round(uptime_hours, 1),
                "total_size_mb": total_size_mb,
                "status": "healthy" if psutil.cpu_percent() < 80 else "warning"
            }

            # 2. 配置与运行状态
            db_status = "running"
            from core.container import container
            try:
                async with container.db.get_session() as session:
                    from sqlalchemy import select, func
                    from models.models import ForwardRule, RuleLog
                    
                    # 转发规则统计
                    total_rules = (await session.execute(select(func.count(ForwardRule.id)))).scalar() or 0
                    active_rules = (await session.execute(select(func.count(ForwardRule.id)).where(ForwardRule.enable_rule == True))).scalar() or 0
                    forward_rules_status = f"{active_rules}/{total_rules} 启用"
                    
                    # 数据记录状态 (检查最近是否有日志条目)
                    recent_logs = (await session.execute(select(func.count(RuleLog.id)).limit(1))).scalar() or 0
                    data_recording_status = "✅ 运行中" if recent_logs > 0 else "💤 待机"
            except Exception as e:
                logger.error(f"AnalyticsService 数据库检查失败: {e}")
                db_status = "unhealthy"
                forward_rules_status = "未知"
                data_recording_status = "未知"

            # 3. 智能去重状态
            dedup_conf = smart_deduplicator.config or {}
            dedup_enabled = dedup_conf.get('enable_time_window') or dedup_conf.get('enable_content_hash')
            smart_dedup_status = "✅ 已开启" if dedup_enabled else "❌ 已关闭"

            # 4. Bot/User Client 状态
            bot_connected = False
            user_connected = False
            try:
                if self.container.bot_client:
                    bot_connected = self.container.bot_client.is_connected()
                if self.container.user_client:
                    user_connected = self.container.user_client.is_connected()
            except Exception as e:
                logger.warning(f"获取 Client 连接状态失败: {e}")

            # 5. 组装返回数据 (对齐 MainMenuRenderer.render_system_hub)
            return {
                "system_resources": system_resources,
                "config_status": {
                    "forward_rules": forward_rules_status,
                    "smart_dedup": smart_dedup_status,
                    "data_recording": data_recording_status
                },
                "overall_status": "healthy" if system_resources["status"] == "healthy" and db_status == "running" else "warning",
                "db": db_status, 
                "bot": "running" if bot_connected else "stopped",
                "user": "running" if user_connected else "stopped",
                "dedup": "running" if dedup_enabled else "stopped"
            }
        except Exception as e:
            logger.error(f"get_system_status 失败: {e}")
            return {
                "system_resources": {"cpu_percent": 0, "memory_percent": 0, "status": "unknown"},
                "config_status": {
                    "forward_rules": "未知",
                    "smart_dedup": "未知",
                    "data_recording": "未知"
                },
                "overall_status": "unknown"
            }

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标和资源占用 (真实数据库统计)"""
        try:
            # 1. 获取系统资源统计
            system_stats = await realtime_stats_cache.get_system_stats(force_refresh=True)
            system_resources = system_stats.get("system_resources", {})

            # 2. 获取转发统计以计算成功率
            forward_stats = await realtime_stats_cache.get_forward_stats()
            today_stats = forward_stats.get("today", {})
            success_rate = 100.0
            if today_stats.get("total_forwards", 0) > 0:
                errors = today_stats.get("error_count", 0)
                success_rate = ((today_stats["total_forwards"] - errors) / today_stats["total_forwards"]) * 100

            # 3. 计算实时 TPS 和 平均响应时间 (基于最近 10 分钟)
            current_tps = 0.0
            avg_response_time = 0.0
            try:
                from sqlalchemy import select, func
                from models.models import RuleLog
                from datetime import datetime, timedelta
                
                cutoff = datetime.utcnow() - timedelta(minutes=10)
                async with self.container.db.get_session() as session:
                    perf_stmt = select(
                        func.count(RuleLog.id).label('count'),
                        func.avg(RuleLog.processing_time).label('avg_time')
                    ).where(RuleLog.created_at >= cutoff)
                    
                    res = await session.execute(perf_stmt)
                    row = res.first()
                    if row and row.count:
                        current_tps = round(row.count / 600, 2) # 过去 10 分钟平均 TPS
                        avg_response_time = round((row.avg_time or 0) / 1000, 3) # 转为秒
            except Exception as e:
                logger.warning(f"计算 TPS/耗时失败: {e}")

            # 4. 获取队列状态
            active_queues = 0
            pending_tasks = 0
            avg_delay = "0s"
            try:
                queue_status = await self.container.task_repo.get_queue_status()
                active_queues = queue_status.get("active_queues", 0)
                pending_tasks = queue_status.get("pending_tasks", 0)
                avg_delay = queue_status.get("avg_delay", "0s")
            except Exception: pass

            return {
                "system_resources": {
                    "cpu_percent": system_resources.get("cpu_percent", 0),
                    "memory_percent": system_resources.get("memory_percent", 0),
                    "status": "healthy" if system_resources.get("cpu_percent", 0) < 80 else "warning",
                },
                "performance": {
                    "success_rate": success_rate,
                    "avg_response_time": avg_response_time or 0, # 默认保底值
                    "current_tps": current_tps,
                    "status": "good" if success_rate > 90 else "poor",
                },
                "queue_status": {
                    "active_queues": active_queues,
                    "pending_tasks": pending_tasks,
                    "avg_delay": avg_delay,
                    "error_rate": f"{(100-success_rate):.1f}%",
                },
            }
        except Exception as e:
            logger.error(f"get_performance_metrics 失败: {e}")
            return {
                "system_resources": {"cpu_percent": 0, "memory_percent": 0},
                "performance": {"success_rate": 0, "avg_response_time": 0, "current_tps": 0},
                "queue_status": {"active_queues": 0},
            }

    async def get_unified_hourly_trend(self, hours: int = 24) -> List[Dict[str, Any]]:
        """跨热冷获取小时级转发趋势"""
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        sql = """
            SELECT 
                strftime('%Y-%m-%dT%H', CAST(created_at AS TIMESTAMP)) as hour,
                COUNT(*) as count
            FROM {table}
            WHERE created_at >= CAST(? AS TIMESTAMP)
            GROUP BY hour
            ORDER BY hour
        """
        return await self.bridge.query_aggregate("rule_logs", sql, [cutoff])

    async def get_daily_summary(self, date_str: str) -> Dict[str, Any]:
        """获取指定日期的每日汇总 (跨热冷查询)"""
        try:
            # 1. 统计转发和错误 (从 rule_logs 跨层)
            sql = """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN action = 'error' THEN 1 ELSE 0 END) as errors
                FROM {table}
                WHERE strftime('%Y-%m-%d', CAST(created_at AS TIMESTAMP)) = ?
            """
            res = await self.bridge.query_aggregate("rule_logs", sql, [date_str])
            row = res[0] if res else {}
            total = row.get('total') or 0
            errors = row.get('errors') or 0

            # 2. 统计活跃聊天 (从 chat_statistics 跨层)
            # 注意: ChatStatistics 也是按天分的
            chat_sql = "SELECT * FROM {table} WHERE date = ? ORDER BY forward_count DESC"
            chats_data = await self.bridge.query_aggregate("chat_statistics", chat_sql, [date_str])
            chats_dict = {str(c.get('chat_id')): c.get('forward_count', 0) for c in chats_data}
            
            # 3. 统计节省流量
            saved_bytes = sum([c.get('saved_traffic_bytes', 0) or 0 for c in chats_data])
            
            return {
                'total_forwards': total,
                'error_count': errors,
                'chats': chats_dict,
                'active_chats': len(chats_dict),
                'date': date_str,
                'saved_traffic_bytes': saved_bytes,
                'is_unified': True
            }
        except Exception as e:
            logger.error(f"get_daily_summary 失败 for {date_str}: {e}")
            return {'total_forwards': 0, 'error_count': 0, 'chats': {}, 'active_chats': 0, 'date': date_str}

    async def get_detailed_stats(self, days: int = 1) -> Dict[str, Any]:
        """获取详细的分时段/分频道统计 (跨热冷查询)"""
        try:
            # 1. 获取最近趋势 (跨层)
            hours = days * 24
            hourly_trend = await self.get_unified_hourly_trend(hours=hours)
            
            # 2. 获取今日汇总
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_summary = await self.get_daily_summary(today_str)
            
            # 3. 获取 Top 规则 (从 rule_statistics 跨层)
            # 由于聚合需要涉及 ForwardRule (SQLite 专有)，我们先查 stats ID，再回 SQLite 查规则名
            stats_sql = """
                SELECT rule_id, SUM(success_count) as success_count, SUM(error_count) as error_count
                FROM {table}
                WHERE date >= ?
                GROUP BY rule_id
                ORDER BY success_count DESC
                LIMIT 5
            """
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            stats_res = await self.bridge.query_aggregate("rule_statistics", stats_sql, [cutoff_date])
            
            top_rules = []
            if stats_res:
                rule_ids = [r['rule_id'] for r in stats_res]
                from models.models import ForwardRule
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                async with self.container.db.get_session() as session:
                    stmt = select(ForwardRule).options(
                        selectinload(ForwardRule.source_chat),
                        selectinload(ForwardRule.target_chat)
                    ).where(ForwardRule.id.in_(rule_ids))
                    res = await session.execute(stmt)
                    rule_map = {r.id: r for r in res.scalars().all()}
                    
                    for s in stats_res:
                        rule_row = rule_map.get(s['rule_id'])
                        
                        rule_name = f"ID {s['rule_id']}"
                        if rule_row:
                            if rule_row.source_chat and rule_row.target_chat:
                                src_name = rule_row.source_chat.title or rule_row.source_chat.name or str(rule_row.source_chat.telegram_chat_id)
                                tgt_name = rule_row.target_chat.title or rule_row.target_chat.name or str(rule_row.target_chat.telegram_chat_id)
                                rule_name = f"{src_name} ➔ {tgt_name}"
                            elif hasattr(rule_row, 'description') and rule_row.description:
                                rule_name = rule_row.description
                                
                        top_rules.append({
                            'rule_id': s['rule_id'],
                            'name': rule_name,
                            'count': s['success_count'],
                            'success_count': s['success_count'],
                            'error_count': s['error_count']
                        })

            # 4. 获取类型分布 (从 rule_logs 聚合)
            type_dist = []
            try:
                type_sql = """
                    SELECT message_type, COUNT(*) as count
                    FROM {table}
                    WHERE strftime('%Y-%m-%d', CAST(created_at AS TIMESTAMP)) >= ?
                    GROUP BY message_type
                """
                type_res = await self.bridge.query_aggregate("rule_logs", type_sql, [cutoff_date])
                
                total_count = sum([r['count'] for r in type_res])
                for r in type_res:
                    m_type_raw = str(r['message_type'] or "text").lower()
                    type_dist.append({
                        "type": m_type_raw,
                        "name": m_type_raw,
                        "count": r['count'],
                        "percentage": round((r['count'] / total_count * 100), 1) if total_count > 0 else 0
                    })
            except Exception as e:
                logger.warning(f"获取类型分布失败: {e}")
            
            if not type_dist:
                 # 回退方案 - 既然用户通过真实数据反馈，则不再生成虚假分布
                 pass
            

            # 5. 获取 Top 频道 (从 chat_statistics 聚合)
            top_chats = []
            try:
                # 先聚合统计
                chat_sql = """
                    SELECT chat_id, SUM(forward_count) as count
                    FROM {table}
                    WHERE date >= ?
                    GROUP BY chat_id
                    ORDER BY count DESC
                    LIMIT 5
                """
                chat_res = await self.bridge.query_aggregate("chat_statistics", chat_sql, [cutoff_date])
                
                if chat_res:
                    chat_ids = [r['chat_id'] for r in chat_res]
                    # 再查详细信息
                    from models.models import Chat
                    from sqlalchemy import select
                    async with self.container.db.get_session() as session:
                        stmt = select(Chat).where(Chat.id.in_(chat_ids))
                        res = await session.execute(stmt)
                        chat_map = {c.id: c for c in res.scalars().all()}
                        
                        for r in chat_res:
                            chat = chat_map.get(r['chat_id'])
                            top_chats.append({
                                "chat_id": str(chat.telegram_chat_id) if chat else str(r['chat_id']),
                                "name": chat.name or chat.title or str(chat.telegram_chat_id) if chat else str(r['chat_id']),
                                "count": r['count']
                            })
            except Exception as e:
                logger.warning(f"获取热门频道失败: {e}")

            return {
                "daily_trends": [
                    {
                        "date": today_str,
                        "total": today_summary.get("total_forwards", 0),
                        "errors": today_summary.get("error_count", 0)
                    }
                ],
                "type_distribution": type_dist,
                "top_chats": top_chats,
                "top_rules": top_rules,
                "time_analysis": {
                    "peak_hours": [row['hour'] for row in sorted(hourly_trend, key=lambda x: x['count'], reverse=True)[:3]],
                    "hourly_today": {row['hour'].split('T')[1] if 'T' in row['hour'] else row['hour']: row['count'] for row in hourly_trend if row['hour'].startswith(today_str)},
                },
            }
        except Exception as e:
            logger.error(f"get_detailed_stats 失败: {e}\n{traceback.format_exc()}")
            return {"daily_trends": [], "type_distribution": [], "top_chats": [], "top_rules": []}

    async def _resolve_chat_name(self, chat_id: Any) -> str:
        """解析聊天名称"""
        try:
            # 尝试从数据库获取
            from models.models import Chat
            from sqlalchemy import select
            async with self.container.db.get_session() as session:
                stmt = select(Chat).where(Chat.telegram_chat_id == str(chat_id))
                res = await session.execute(stmt)
                chat = res.scalar_one_or_none()
                if chat and chat.name:
                    return chat.name
            
            # 尝试从 chat_info_service 获取
            name = await self.container.chat_info_service.get_chat_name(int(chat_id))
            if name:
                return name
        except Exception:
            pass
        return str(chat_id)[:12]

    async def detect_anomalies(self) -> Dict[str, Any]:
        """系统异常检测 (基于实时指标)"""
        try:
            status = await self.get_system_status()
            anomalies = []
            recommendations = []

            # 1. 基础服务状态检查
            if status.get("db") != "running":
                anomalies.append({
                    "type": "database",
                    "severity": "critical",
                    "message": "数据库连接异常",
                    "icon": "🔴"
                })
                recommendations.append("请检查数据库文件权限或磁盘空间")

            if status.get("bot") != "running":
                anomalies.append({
                    "type": "bot",
                    "severity": "warning",
                    "message": "Bot 服务心跳超时 (可能已离线)",
                    "icon": "⚠️"
                })
                recommendations.append("请尝试重启程序或检查 Telegram API 连接")

            # 2. 转发成功率检查
            perf = await self.get_performance_metrics()
            success_rate = perf.get('performance', {}).get('success_rate', 100)
            if success_rate < 80:
                anomalies.append({
                    "type": "performance",
                    "severity": "high",
                    "message": f"转发成功率偏低: {success_rate:.1f}%",
                    "icon": "📉"
                })
                recommendations.append("建议检查规则配置是否正确或是否触发了 Telegram Flood")

            # 3. 资源监控
            cpu = perf.get('system_resources', {}).get('cpu_percent', 0)
            if cpu > 90:
                 anomalies.append({
                        "type": "resource",
                        "severity": "high",
                        "message": "CPU 负载异常偏高",
                        "icon": "🔥"
                    })
                 recommendations.append("检查是否有死循环任务或减少并发数")

            score = 100.0 - (len(anomalies) * 25)
            return {
                "anomalies": anomalies,
                "recommendations": recommendations,
                "health_score": max(0.0, score),
                "status": "healthy" if not anomalies else ("warning" if score > 50 else "critical"),
            }
        except Exception as e:
            logger.error(f"detect_anomalies 失败: {e}")
            return {"anomalies": [], "health_score": 0.0, "status": "unknown"}

    async def check_data_health(self) -> Dict[str, Any]:
        """检查数据一致性与存储健康度"""
        try:
            from sqlalchemy import select, func
            from models.models import RuleLog, MediaSignature
            
            async with self.container.db.get_session() as session:
                log_count = (await session.execute(select(func.count(RuleLog.id)))).scalar() or 0
                sig_count = (await session.execute(select(func.count(MediaSignature.id)))).scalar() or 0
                
            return {
                "total_records": log_count,
                "media_signatures": sig_count,
                "available_days": 30, # 假设，可以通过查询最早日志得知
                "data_health": "good" if log_count > 0 else "nascent",
                "message": f"系统记录运行正常, 已记录 {log_count} 条转发日志",
            }
        except Exception:
            return {"data_health": "unknown", "message": "无法读取统计数据"}

    async def get_detailed_analytics(self, days: int = 7) -> Dict[str, Any]:
        """获取详细的分析数据 (用于导出和详细展示)
        
        Args:
            days: 统计天数
            
        Returns:
            详细的分析数据字典
        """
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import select
            from models.models import RuleStatistics, ChatStatistics
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 1. 按日期统计转发数
            daily_stats = []
            for i in range(days + 1):
                date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
                summary = await self.get_daily_summary(date)
                daily_stats.append({
                    'date': date,
                    'total_forwards': summary.get('total_forwards', 0),
                    'error_count': summary.get('error_count', 0),
                    'active_chats': summary.get('active_chats', 0),
                    'saved_traffic_bytes': summary.get('saved_traffic_bytes', 0)
                })
                
            # 2. 获取聚合详情 (包含 top_rules, type_distribution, top_chats)
            detailed_stats = await self.get_detailed_stats(days=days)
            top_rules = detailed_stats.get('top_rules', [])
            top_chats = detailed_stats.get('top_chats', [])
            type_dist = detailed_stats.get('type_distribution', [])
            
            return {
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'days': days
                },
                'daily_stats': daily_stats,
                'top_rules': top_rules,
                'top_chats': top_chats,
                'type_distribution': type_dist,
                'summary': {
                    'total_forwards': sum(d['total_forwards'] for d in daily_stats),
                    'total_errors': sum(d['error_count'] for d in daily_stats),
                    'avg_daily_forwards': sum(d['total_forwards'] for d in daily_stats) / days if days > 0 else 0
                }
            }
        except Exception as e:
            logger.error(f"get_detailed_analytics 失败: {e}\n{traceback.format_exc()}")
            return {
                'period': {'days': days},
                'daily_stats': [],
                'top_rules': [],
                'top_chats': [],
                'summary': {'total_forwards': 0, 'total_errors': 0}
            }

    async def search_records(self, query: str, limit: int = 50) -> Dict[str, Any]:
        """搜索转发记录 (支持跨热冷查询)"""
        try:
            where_sql = "(message_text LIKE ? OR action LIKE ?)"
            params = [f'%{query}%', f'%{query}%']
            
            rows = await self.bridge.query_unified(
                "rule_logs",
                where_sql=where_sql,
                params=params,
                limit=limit,
                order_by="created_at DESC"
            )
            
            records = []
            # 预加载缓存规则
            from models.models import ForwardRule, Chat
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload
            
            # 获取所有涉及的 rule_id
            rule_ids = list(set([r.get('rule_id') for r in rows if r.get('rule_id')]))
            rule_map = {}
            
            if rule_ids:
                async with self.container.db.get_session() as session:
                    stmt = select(ForwardRule).options(
                        joinedload(ForwardRule.source_chat),
                        joinedload(ForwardRule.target_chat)
                    ).where(ForwardRule.id.in_(rule_ids))
                    res = await session.execute(stmt)
                    for rule in res.scalars().all():
                        rule_map[rule.id] = rule

            for log in rows:
                rule = rule_map.get(log.get('rule_id'))
                source_title = "未知"
                target_title = "未知"
                
                if rule:
                    if rule.source_chat:
                        c = rule.source_chat
                        source_title = c.title or c.name or c.username or str(c.telegram_chat_id)
                    else:
                        source_title = str(rule.source_chat_id)
                        
                    if rule.target_chat:
                        c = rule.target_chat
                        target_title = c.title or c.name or c.username or str(c.telegram_chat_id)
                    else:
                        target_title = str(rule.target_chat_id)
                
                created_at = log.get('created_at')
                if isinstance(created_at, datetime):
                    created_at_str = created_at.replace(tzinfo=timezone.utc).isoformat()
                else:
                    created_at_str = str(created_at)

                records.append({
                    'id': log.get('id'),
                    'rule_id': log.get('rule_id'),
                    'action': log.get('action'),
                    'message_text': (log.get('message_text') or '')[:100],
                    'created_at': created_at_str,
                    'source_chat_id': source_title,
                    'target_chat_id': target_title,
                    'source_chat': source_title,
                    'target_chat': target_title,
                    'source_title': source_title,
                    'target_title': target_title
                })

            return {
                'query': query,
                'total_results': len(records),
                'records': records,
                'limit': limit,
                'is_unified': True
            }
        except Exception as e:
            logger.error(f"search_records 失败: {e}\n{traceback.format_exc()}")
            return {
                'query': query,
                'total_results': 0,
                'records': [],
                'error': str(e)
            }


    async def export_logs_to_csv(self, rule_id: Optional[int] = None, days: int = 7) -> Optional[Path]:
        """导出转发日志到 CSV (跨热冷)"""
        try:
            import csv
            import os
            import time
            from core.config import settings
            
            os.makedirs(settings.TEMP_DIR, exist_ok=True)
            suffix = f"rule_{rule_id}" if rule_id else "all"
            export_path = settings.TEMP_DIR / f"export_{suffix}_{int(time.time())}.csv"
            
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            where_sql = "created_at >= CAST(? AS TIMESTAMP)"
            params = [cutoff]
            
            if rule_id:
                where_sql += " AND rule_id = ?"
                params.append(rule_id)
            
            # 使用 bridge 跨热冷查询
            logs = await self.bridge.query_unified(
                "rule_logs",
                where_sql=where_sql,
                params=params,
                limit=10000, # 限制 10000 条导出
                order_by="created_at DESC"
            )
            
            if not logs:
                return None
                
            headers = ["ID", "Time", "RuleID", "Type", "Action", "Latency", "Message"]
            with open(export_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for log in logs:
                    created_at = log.get('created_at')
                    time_str = created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created_at, 'strftime') else str(created_at)
                    writer.writerow([
                        log.get('id'),
                        time_str,
                        log.get('rule_id'),
                        log.get('message_type'),
                        log.get('action'),
                        f"{log.get('processing_time', 0)/1000:.3f}s",
                        (log.get('message_text') or '')[:200]
                    ])
            
            return export_path
        except Exception as e:
            logger.error(f"Export logs to CSV failed: {e}\n{traceback.format_exc()}")
            return None

# 创建单例实例
analytics_service = AnalyticsService()
