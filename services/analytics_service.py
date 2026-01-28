import logging
import traceback
from datetime import datetime
from typing import Dict, Any

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

    @property
    def container(self):
        if self._container:
            return self._container
        from core.container import container
        return container

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
            
            # 2. 获取转发统计 (从 ForwardService 获取今日统计)
            forward_stats = {'total_forwards': 0}
            try:
                from services.forward_service import forward_service
                fs = await forward_service.get_forward_stats()
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

            return {
                'overview': overview,
                'forward_stats': forward_stats,
                'dedup_stats': dedup_stats,
                'hll_stats': hll_stats
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
        """获取各项服务运行状态"""
        try:
            # 1. 数据库状态
            from models.models import get_db_health
            db = {}
            try:
                db = get_db_health()
            except Exception:
                db = {}
            db_status = 'running' if bool(db.get('connected')) else 'stopped'
            
            # 2. Bot 状态
            bot_status = 'unknown'
            try:
                hb = get_heartbeat()
                age = float(hb.get('age_seconds') or 9999)
                hbs = str(hb.get('status') or '')
                if hbs == 'running' and age < 180:
                    bot_status = 'running'
                elif hbs:
                    bot_status = 'stopped'
            except Exception:
                bot_status = 'unknown'
            
            # 3. 去重服务状态
            try:
                dedup_conf = smart_deduplicator.config or {}
                # 如果有任何去重手段开启或有缓存，则认为去重服务在运行
                dedup_enabled = bool(dedup_conf.get('enable_time_window')) or \
                                bool(dedup_conf.get('enable_content_hash'))
                dedup_state = 'running' if dedup_enabled else 'stopped'
            except Exception:
                dedup_state = 'unknown'
                
            return {
                'db': db_status,
                'bot': bot_status,
                'dedup': dedup_state
            }
        except Exception as e:
            logger.error(f"get_system_status 失败: {e}")
            return {'db': 'unknown', 'bot': 'unknown', 'dedup': 'unknown'}

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标和资源占用"""
        try:
            # 获取实时统计数据

            # 获取系统资源统计
            system_stats = await realtime_stats_cache.get_system_stats(
                force_refresh=True
            )
            system_resources = system_stats.get("system_resources", {})

            # 获取转发统计以计算性能指标
            forward_stats = await realtime_stats_cache.get_forward_stats()
            today_stats = forward_stats.get("today", {})

            # 计算性能指标
            success_rate = 100.0
            if "total_forwards" in today_stats and today_stats["total_forwards"] > 0:
                errors = today_stats.get("error_count", 0)
                success_rate = (
                    (today_stats["total_forwards"] - errors)
                    / today_stats["total_forwards"]
                ) * 100

            # 获取队列状态
            active_queues = 0
            pending_tasks = 0
            try:
                queue_status = await self.container.task_repo.get_queue_status()
                active_queues = queue_status.get("active_queues", 0)
                pending_tasks = queue_status.get("pending_tasks", 0)
            except Exception:
                pass

            return {
                "system_resources": {
                    "cpu_percent": system_resources.get("cpu_percent", 0),
                    "memory_percent": system_resources.get("memory_percent", 0),
                    "status": "healthy"
                    if system_resources.get("cpu_percent", 0) < 80
                    else "warning",
                },
                "performance": {
                    "success_rate": success_rate,
                    "avg_response_time": 0.5,  # 模拟值
                    "current_tps": 12.5,  # 模拟值
                    "status": "good" if success_rate > 90 else "poor",
                },
                "queue_status": {
                    "active_queues": active_queues,
                    "pending_tasks": pending_tasks,
                    "error_rate": f"{(100-success_rate):.1f}%",
                },
            }
        except Exception as e:
            logger.error(f"get_performance_metrics 失败: {e}")
            return {
                "system_resources": {"cpu_percent": 0, "memory_percent": 0},
                "performance": {"success_rate": 0},
                "queue_status": {"active_queues": 0},
            }

    async def get_daily_summary(self, date_str: str) -> Dict[str, Any]:
        """获取指定日期的每日汇总 (从数据库获取)"""
        try:
            from sqlalchemy import select, func
            from models.models import RuleLog, ChatStatistics

            async with self.container.db.session() as session:
                # 1. 统计总转发数和错误数 (从 RuleLog)
                stats_stmt = (
                    select(
                        func.count(RuleLog.id).label('total'),
                        func.sum(RuleLog.action == 'error').label('errors')
                    )
                    .where(func.strftime('%Y-%m-%d', RuleLog.created_at) == date_str)
                )
                stats_res = await session.execute(stats_stmt)
                row = stats_res.first()
                total = row.total if row and row.total else 0
                errors = row.errors if row and row.errors else 0

                # 2. 统计活跃聊天 (从 ChatStatistics)
                chats_stmt = (
                    select(ChatStatistics)
                    .where(ChatStatistics.date == date_str)
                    .order_by(ChatStatistics.forward_count.desc())
                )
                chats_res = await session.execute(chats_stmt)
                chats_data = chats_res.scalars().all()
                
                chats_dict = {str(c.chat_id): c.forward_count for c in chats_data}
                
                return {
                    'total_forwards': total,
                    'error_count': errors,
                    'chats': chats_dict,
                    'active_chats': len(chats_dict),
                    'date': date_str
                }
        except Exception as e:
            logger.error(f"get_daily_summary 失败 for {date_str}: {e}")
            return {'total_forwards': 0, 'error_count': 0, 'chats': {}, 'active_chats': 0, 'date': date_str}

    async def get_detailed_stats(self, days: int = 1) -> Dict[str, Any]:
        """获取详细的分时段/分频道统计 (从数据库获取)"""
        try:
            # 1. 获取最近 24 小时趋势
            hourly_trend = await self.container.stats_repo.get_hourly_trend(hours=24)
            
            # 2. 获取今日汇总
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_summary = await self.get_daily_summary(today_str)
            
            # 3. 获取 Top 规则 (从 RuleStatistics)
            from models.models import RuleStatistics, ForwardRule
            from sqlalchemy import select
            
            top_rules = []
            async with self.container.db.session() as session:
                stmt = (
                    select(RuleStatistics, ForwardRule)
                    .join(ForwardRule, RuleStatistics.rule_id == ForwardRule.id)
                    .where(RuleStatistics.date == today_str)
                    .order_by(RuleStatistics.forwarded_count.desc())
                    .limit(5)
                )
                res = await session.execute(stmt)
                for row in res:
                    # SQLAlchemy 返回的是元组 (RuleStatistics, ForwardRule)
                    stats_row, rule_row = row
                    top_rules.append({
                        'rule_id': rule_row.id,
                        'name': getattr(rule_row, 'name', f"Rule {rule_row.id}"),
                        'count': stats_row.forwarded_count
                    })

            # 4. 获取类型分布 (暂时根据结果中的关键词模糊估计)
            # 真正准确的类型分布需要 SenderMiddleware 传入 type
            
            return {
                "daily_trends": [
                    {
                        "date": today_str,
                        "total": today_summary.get("total_forwards", 0),
                        "errors": today_summary.get("error_count", 0)
                    }
                ],
                "type_distribution": [
                    {"type": "Text", "count": int(today_summary.get("total_forwards", 0) * 0.7), "percentage": 70},
                    {"type": "Media", "count": int(today_summary.get("total_forwards", 0) * 0.3), "percentage": 30},
                ],
                "top_chats": [
                    {"chat_id": cid, "count": count} 
                    for cid, count in list(today_summary.get("chats", {}).items())[:5]
                ],
                "top_rules": top_rules,
                "time_analysis": {
                    "peak_hours": [row['hour'] for row in sorted(hourly_trend, key=lambda x: x['count'], reverse=True)[:3]],
                    "hourly_today": {row['hour'].split('T')[1] if 'T' in row['hour'] else row['hour']: row['count'] for row in hourly_trend if row['hour'].startswith(today_str)},
                },
            }
        except Exception as e:
            logger.error(f"get_detailed_stats 失败: {e}\n{traceback.format_exc()}")
            return {"daily_trends": [], "type_distribution": []}

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
            
            async with self.container.db.session() as session:
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
            
            async with self.container.db.session() as session:
                # 1. 按日期统计转发数
                daily_stats = []
                for i in range(days):
                    date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
                    summary = await self.get_daily_summary(date)
                    daily_stats.append({
                        'date': date,
                        'total_forwards': summary.get('total_forwards', 0),
                        'error_count': summary.get('error_count', 0),
                        'active_chats': summary.get('active_chats', 0)
                    })
                
                # 2. 规则统计
                stmt = select(RuleStatistics).order_by(RuleStatistics.forwarded_count.desc()).limit(10)
                result = await session.execute(stmt)
                rule_stats = result.scalars().all()
                
                top_rules = [{
                    'rule_id': rs.rule_id,
                    'forwarded_count': rs.forwarded_count,
                    'error_count': rs.error_count,
                    'date': rs.date
                } for rs in rule_stats]
                
                # 3. 聊天统计
                stmt = select(ChatStatistics).order_by(ChatStatistics.message_count.desc()).limit(10)
                result = await session.execute(stmt)
                chat_stats = result.scalars().all()
                
                top_chats = [{
                    'chat_id': cs.chat_id,
                    'message_count': cs.message_count,
                    'forward_count': cs.forward_count,
                    'date': cs.date
                } for cs in chat_stats]
                
                return {
                    'period': {
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'days': days
                    },
                    'daily_stats': daily_stats,
                    'top_rules': top_rules,
                    'top_chats': top_chats,
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
        """搜索转发记录
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            搜索结果字典
        """
        try:
            from sqlalchemy import select, or_
            from models.models import RuleLog
            
            async with self.container.db.session() as session:
                # 搜索规则日志
                stmt = select(RuleLog).filter(
                    or_(
                        RuleLog.message_text.like(f'%{query}%'),
                        RuleLog.action.like(f'%{query}%')
                    )
                ).order_by(RuleLog.created_at.desc()).limit(limit)
                
                result = await session.execute(stmt)
                logs = result.scalars().all()
                
                records = [{
                    'id': log.id,
                    'rule_id': log.rule_id,
                    'action': log.action,
                    'message_text': log.message_text[:100] if log.message_text else '',
                    'created_at': log.created_at,
                    'source_chat_id': log.source_chat_id,
                    'target_chat_id': log.target_chat_id
                } for log in logs]
                
                return {
                    'query': query,
                    'total_results': len(records),
                    'records': records,
                    'limit': limit
                }
        except Exception as e:
            logger.error(f"search_records 失败: {e}\n{traceback.format_exc()}")
            return {
                'query': query,
                'total_results': 0,
                'records': [],
                'error': str(e)
            }


# 创建单例实例
analytics_service = AnalyticsService()