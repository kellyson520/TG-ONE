import logging
import traceback
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
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

    async def get_daily_summary(self, date_str: str) -> Dict[str, Any]:
        """获取指定日期的每日汇总 (从数据库获取)"""
        try:
            from sqlalchemy import select, func
            from models.models import RuleLog, ChatStatistics

            async with self.container.db.get_session() as session:
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
                
                # 3. 统计节省流量 (从 ChatStatistics)
                traffic_stmt = (
                    select(func.sum(ChatStatistics.saved_traffic_bytes))
                    .where(ChatStatistics.date == date_str)
                )
                saved_bytes = (await session.execute(traffic_stmt)).scalar() or 0
                
                return {
                    'total_forwards': total,
                    'error_count': errors,
                    'chats': chats_dict,
                    'active_chats': len(chats_dict),
                    'date': date_str,
                    'saved_traffic_bytes': saved_bytes
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
            async with self.container.db.get_session() as session:
                stmt = (
                    select(RuleStatistics, ForwardRule)
                    .join(ForwardRule, RuleStatistics.rule_id == ForwardRule.id)
                    .where(RuleStatistics.date == today_str)
                    .order_by(RuleStatistics.success_count.desc())
                    .limit(5)
                )
                res = await session.execute(stmt)
                for row in res:
                    # SQLAlchemy 返回的是元组 (RuleStatistics, ForwardRule)
                    stats_row, rule_row = row
                    top_rules.append({
                        'rule_id': rule_row.id,
                        'name': getattr(rule_row, 'name', f"Rule {rule_row.id}"),
                        'count': stats_row.success_count
                    })

            # 4. 获取类型分布 (从 RuleLog 真实聚合)
            type_dist = []
            try:
                from sqlalchemy import select, func
                from models.models import RuleLog
                async with self.container.db.get_session() as session:
                    type_stmt = select(
                        RuleLog.message_type,
                        func.count(RuleLog.id).label('count')
                    ).where(
                        func.strftime('%Y-%m-%d', RuleLog.created_at) == today_str
                    ).group_by(RuleLog.message_type)
                    
                    type_res = await session.execute(type_stmt)
                    total_count = 0
                    temp_dist = []
                    for row in type_res:
                        # 修复: 确保 None/Unknown 映射为 "Text" (常见情况)
                        m_type = row.message_type
                        if not m_type or m_type.lower() == 'unknown':
                            m_type = "Text"
                        else:
                            m_type = m_type.capitalize()
                            
                        count = row.count or 0
                        total_count += count
                        
                        # 合并同名类型 (如 'text' 和 'Text')
                        found = False
                        for item in temp_dist:
                            if item["name"] == m_type:
                                item["count"] += count
                                found = True
                                break
                        if not found:
                            temp_dist.append({"name": m_type, "count": count})
                    
                    if total_count > 0:
                        for item in temp_dist:
                            item["percentage"] = round((item["count"] / total_count) * 100, 1)
                            type_dist.append(item)
            except Exception as e:
                logger.warning(f"获取类型分布失败: {e}")
            
            if not type_dist:
                 # 回退方案 - 既然用户通过真实数据反馈，则不再生成虚假分布
                 pass
            
            return {
                "daily_trends": [
                    {
                        "date": today_str,
                        "total": today_summary.get("total_forwards", 0),
                        "errors": today_summary.get("error_count", 0)
                    }
                ],
                "type_distribution": type_dist,
                "top_chats": [
                    {"chat_id": cid, "name": await self._resolve_chat_name(cid), "count": count} 
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
            
            async with self.container.db.get_session() as session:
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
                stmt = select(RuleStatistics).order_by(RuleStatistics.success_count.desc()).limit(10)
                result = await session.execute(stmt)
                rule_stats = result.scalars().all()
                
                top_rules = [{
                    'rule_id': rs.rule_id,
                    'success_count': rs.success_count,
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
            from models.models import RuleLog, ForwardRule
            
            from sqlalchemy.orm import joinedload
            async with self.container.db.get_session() as session:
                # 搜索规则日志，预加载关联的规则以及规则关联的聊天实体，确保显示名称而非 "未知"
                stmt = select(RuleLog).options(
                    joinedload(RuleLog.rule).joinedload(ForwardRule.source_chat),
                    joinedload(RuleLog.rule).joinedload(ForwardRule.target_chat)
                ).filter(
                    or_(
                        RuleLog.message_text.like(f'%{query}%'),
                        RuleLog.action.like(f'%{query}%')
                    )
                ).order_by(RuleLog.created_at.desc()).limit(limit)
                
                result = await session.execute(stmt)
                logs = result.scalars().all()
                
                records = []
                for log in logs:
                    source_title = "未知"
                    target_title = "未知"
                    
                    if log.rule:
                        if log.rule.source_chat:
                            c = log.rule.source_chat
                            source_title = c.title or c.name or c.username or str(c.telegram_chat_id)
                        else:
                            source_title = str(log.rule.source_chat_id)
                            
                        if log.rule.target_chat:
                            c = log.rule.target_chat
                            target_title = c.title or c.name or c.username or str(c.telegram_chat_id)
                        else:
                            target_title = str(log.rule.target_chat_id)
                    
                    records.append({
                        'id': log.id,
                        'rule_id': log.rule_id,
                        'action': log.action,
                        'message_text': log.message_text[:100] if log.message_text else '',
                        'created_at': log.created_at.replace(tzinfo=timezone.utc).isoformat() if hasattr(log.created_at, 'isoformat') else str(log.created_at),
                        'source_chat_id': source_title, # 保留旧字段但填入名称以修复显示
                        'target_chat_id': target_title,
                        'source_chat': source_title,    # 新增对齐 RuleDTOMapper
                        'target_chat': target_title,
                        'source_title': source_title,   # 冗余字段提高兼容性
                        'target_title': target_title
                    })
                
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