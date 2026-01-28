"""
数据库性能监控与分析系统
提供实时性能监控、慢查询分析、资源使用统计等功能
"""

import threading
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

import asyncio
import os
import psutil
import time
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from typing import Any, Dict, List, Optional

from models.models import get_engine
from core.logging import get_logger
from core.cache.unified_cache import get_smart_cache

logger = get_logger(__name__)


@dataclass
class QueryMetrics:
    """查询指标"""

    sql: str
    duration: float
    timestamp: datetime
    result_count: Optional[int] = None
    error: Optional[str] = None
    connection_id: Optional[str] = None
    thread_id: Optional[int] = None


@dataclass
class DatabaseMetrics:
    """数据库指标"""

    timestamp: datetime
    connection_count: int
    active_queries: int
    db_size: int
    wal_size: int
    cache_hit_ratio: float
    cpu_usage: float
    memory_usage: float
    disk_io_read: int
    disk_io_write: int


class QueryProfiler:
    """查询性能分析器"""

    def __init__(self, max_history: int = 10000):
        self.query_history = deque(maxlen=max_history)
        self.slow_query_threshold = 1.0  # 1秒
        self.slow_queries = deque(maxlen=1000)
        self.query_stats = defaultdict(
            lambda: {"count": 0, "total_time": 0, "avg_time": 0}
        )
        self.lock = threading.RLock()

    def record_query(
        self,
        sql: str,
        duration: float,
        result_count: Optional[int] = None,
        error: Optional[str] = None,
    ):
        """记录查询"""
        metrics = QueryMetrics(
            sql=sql,
            duration=duration,
            timestamp=datetime.utcnow(),
            result_count=result_count,
            error=error,
            thread_id=threading.get_ident(),
        )

        with self.lock:
            self.query_history.append(metrics)

            # 慢查询检测
            if duration > self.slow_query_threshold:
                self.slow_queries.append(metrics)

            # 统计信息更新
            normalized_sql = self._normalize_sql(sql)
            stats = self.query_stats[normalized_sql]
            stats["count"] += 1
            stats["total_time"] += duration
            stats["avg_time"] = stats["total_time"] / stats["count"]

    def _normalize_sql(self, sql: str) -> str:
        """标准化SQL语句"""
        # 简单的SQL标准化：移除参数值，保留结构
        import re

        # 移除注释
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        sql = re.sub(r"--.*", "", sql)

        # 替换字符串和数字参数
        sql = re.sub(r"'[^']*'", "'?'", sql)
        sql = re.sub(r"\b\d+\b", "?", sql)

        # 标准化空白字符
        sql = re.sub(r"\s+", " ", sql.strip())

        return sql.upper()

    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取慢查询"""
        with self.lock:
            slow_list = list(self.slow_queries)

        # 按执行时间排序
        slow_list.sort(key=lambda x: x.duration, reverse=True)

        return [
            {
                "sql": query.sql,
                "duration": query.duration,
                "timestamp": query.timestamp.isoformat(),
                "result_count": query.result_count,
                "error": query.error,
            }
            for query in slow_list[:limit]
        ]

    def get_top_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取TOP查询（按执行次数）"""
        with self.lock:
            sorted_queries = sorted(
                self.query_stats.items(), key=lambda x: x[1]["count"], reverse=True
            )

        return [
            {
                "sql": sql,
                "count": stats["count"],
                "total_time": stats["total_time"],
                "avg_time": stats["avg_time"],
            }
            for sql, stats in sorted_queries[:limit]
        ]

    def get_query_timeline(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """获取查询时间线"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        with self.lock:
            recent_queries = [q for q in self.query_history if q.timestamp > cutoff]

        # 按分钟聚合
        timeline = defaultdict(lambda: {"count": 0, "total_time": 0, "errors": 0})

        for query in recent_queries:
            minute_key = query.timestamp.strftime("%Y-%m-%d %H:%M")
            timeline[minute_key]["count"] += 1
            timeline[minute_key]["total_time"] += query.duration
            if query.error:
                timeline[minute_key]["errors"] += 1

        # 转换为列表并计算平均时间
        result = []
        for minute, stats in sorted(timeline.items()):
            stats["avg_time"] = (
                stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
            )
            result.append({"minute": minute, **stats})

        return result


class DatabaseMonitor:
    """数据库监控器"""

    def __init__(self):
        self.metrics_history = deque(maxlen=1440)  # 保留24小时数据（每分钟一个点）
        self.lock = threading.RLock()
        self.monitoring = False
        self.monitor_task = None

    async def start_monitoring(self, interval: int = 60):
        """开始异步监控"""
        if self.monitoring:
            return

        self.monitoring = True
        logger.info("Database monitoring initiated (Async).")
        while self.monitoring:
            try:
                # 收集指标可能涉及 DB IO，在线程池中执行以避免阻塞 Loop
                loop = asyncio.get_running_loop()
                metrics = await loop.run_in_executor(None, self._collect_metrics)
                
                with self.lock:
                    self.metrics_history.append(metrics)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                self.monitoring = False
                break
            except Exception as e:
                logger.error(f"Monitoring collection error: {e}")
                await asyncio.sleep(interval)

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        logger.info("Database monitoring stopped")

    def _collect_metrics(self) -> DatabaseMetrics:
        """收集指标"""
        try:
            # 数据库大小
            db_size = 0
            wal_size = 0

            try:
                with get_engine().connect() as conn:
                    size_result = conn.execute(
                        text(
                            "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
                        )
                    ).fetchone()
                    db_size = size_result[0] if size_result else 0
            except Exception:
                pass

            # WAL文件大小
            from pathlib import Path

            wal_file = (
                Path(__file__).resolve().parent.parent / "db" / "forward.db-wal"
            ).resolve()
            if wal_file.exists():
                wal_size = os.path.getsize(str(wal_file))

            # 系统资源
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()

            # 磁盘I/O
            disk_io = psutil.disk_io_counters()

            return DatabaseMetrics(
                timestamp=datetime.utcnow(),
                connection_count=self._get_connection_count(),
                active_queries=0,  # SQLite doesn't provide this easily
                db_size=db_size,
                wal_size=wal_size,
                cache_hit_ratio=self._get_cache_hit_ratio(),
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                disk_io_read=disk_io.read_bytes if disk_io else 0,
                disk_io_write=disk_io.write_bytes if disk_io else 0,
            )

        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return DatabaseMetrics(
                timestamp=datetime.utcnow(),
                connection_count=0,
                active_queries=0,
                db_size=0,
                wal_size=0,
                cache_hit_ratio=0.0,
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_io_read=0,
                disk_io_write=0,
            )

    def _get_connection_count(self) -> int:
        """获取连接数"""
        try:
            engine = get_engine()
            pool = engine.pool
            return pool.checkedout() if hasattr(pool, "checkedout") else 0
        except Exception:
            return 0

    def _get_cache_hit_ratio(self) -> float:
        """获取缓存命中率"""
        try:
            with get_engine().connect() as conn:
                stats = conn.execute(text("PRAGMA cache_size")).fetchone()
                # SQLite doesn't provide hit ratio directly, estimate based on cache size
                if stats and stats[0] > 0:
                    return 0.85  # 估算值
                return 0.0
        except Exception:
            return 0.0

    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """获取指标摘要"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        with self.lock:
            recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff]

        if not recent_metrics:
            return {}

        # 计算统计信息
        cpu_values = [m.cpu_usage for m in recent_metrics]
        memory_values = [m.memory_usage for m in recent_metrics]
        db_sizes = [m.db_size for m in recent_metrics]

        return {
            "time_range": f"{hours}h",
            "sample_count": len(recent_metrics),
            "cpu_usage": {
                "avg": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values),
            },
            "memory_usage": {
                "avg": sum(memory_values) / len(memory_values),
                "max": max(memory_values),
                "min": min(memory_values),
            },
            "database_size": {
                "current": db_sizes[-1] if db_sizes else 0,
                "change": db_sizes[-1] - db_sizes[0] if len(db_sizes) > 1 else 0,
            },
            "connection_count": {
                "avg": sum(m.connection_count for m in recent_metrics)
                / len(recent_metrics),
                "max": max(m.connection_count for m in recent_metrics),
            },
        }

    def get_alerts(self) -> List[Dict[str, Any]]:
        """获取告警"""
        alerts = []

        with self.lock:
            if not self.metrics_history:
                return alerts

            latest = self.metrics_history[-1]

        # CPU使用率告警
        if latest.cpu_usage > 80:
            alerts.append(
                {
                    "type": "cpu_high",
                    "severity": "warning" if latest.cpu_usage < 90 else "critical",
                    "message": f"CPU usage is {latest.cpu_usage:.1f}%",
                    "value": latest.cpu_usage,
                    "threshold": 80,
                }
            )

        # 内存使用率告警
        if latest.memory_usage > 85:
            alerts.append(
                {
                    "type": "memory_high",
                    "severity": "warning" if latest.memory_usage < 95 else "critical",
                    "message": f"Memory usage is {latest.memory_usage:.1f}%",
                    "value": latest.memory_usage,
                    "threshold": 85,
                }
            )

        # 数据库大小告警
        db_size_mb = latest.db_size / (1024 * 1024)
        if db_size_mb > 1000:  # 1GB
            alerts.append(
                {
                    "type": "db_size_large",
                    "severity": "warning",
                    "message": f"Database size is {db_size_mb:.1f}MB",
                    "value": db_size_mb,
                    "threshold": 1000,
                }
            )

        # WAL文件大小告警
        wal_size_mb = latest.wal_size / (1024 * 1024)
        if wal_size_mb > 100:  # 100MB
            alerts.append(
                {
                    "type": "wal_size_large",
                    "severity": "warning",
                    "message": f"WAL file size is {wal_size_mb:.1f}MB",
                    "value": wal_size_mb,
                    "threshold": 100,
                }
            )

        return alerts


class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self):
        self.cache = get_smart_cache("performance_analysis", l1_ttl=300, l2_ttl=1800)

    def analyze_query_patterns(self, profiler: QueryProfiler) -> Dict[str, Any]:
        """分析查询模式"""
        cache_key = "query_patterns_analysis"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        analysis = {"summary": {}, "recommendations": [], "patterns": {}}

        # 获取查询统计
        top_queries = profiler.get_top_queries(20)
        slow_queries = profiler.get_slow_queries(10)

        # 分析查询频率
        if top_queries:
            total_queries = sum(q["count"] for q in top_queries)
            analysis["summary"]["total_queries"] = total_queries
            analysis["summary"]["unique_patterns"] = len(top_queries)

            # 找出热点查询
            hot_queries = [
                q for q in top_queries if q["count"] > total_queries * 0.05
            ]  # 超过5%的查询
            analysis["patterns"]["hot_queries"] = len(hot_queries)

            # 分析慢查询
            if slow_queries:
                avg_slow_time = sum(q["duration"] for q in slow_queries) / len(
                    slow_queries
                )
                analysis["summary"]["slow_query_avg_time"] = avg_slow_time
                analysis["summary"]["slow_query_count"] = len(slow_queries)

                # 慢查询建议
                for slow_query in slow_queries[:3]:  # 最慢的3个
                    if "SELECT" in slow_query["sql"].upper():
                        if "WHERE" not in slow_query["sql"].upper():
                            analysis["recommendations"].append(
                                {
                                    "type": "missing_where_clause",
                                    "query": slow_query["sql"][:100] + "...",
                                    "suggestion": "Add WHERE clause to limit result set",
                                }
                            )
                        elif "ORDER BY" in slow_query["sql"].upper():
                            analysis["recommendations"].append(
                                {
                                    "type": "missing_index_for_order",
                                    "query": slow_query["sql"][:100] + "...",
                                    "suggestion": "Add index for ORDER BY column",
                                }
                            )

        # 缓存结果
        self.cache.set(cache_key, analysis, ttl=300)
        return analysis

    def generate_performance_report(
        self, profiler: QueryProfiler, monitor: DatabaseMonitor
    ) -> Dict[str, Any]:
        """生成性能报告"""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "query_analysis": self.analyze_query_patterns(profiler),
            "system_metrics": monitor.get_metrics_summary(hours=1),
            "alerts": monitor.get_alerts(),
            "recommendations": [],
        }

        # 综合建议
        query_analysis = report["query_analysis"]
        system_metrics = report["system_metrics"]

        # 基于查询分析的建议
        if query_analysis.get("summary", {}).get("slow_query_count", 0) > 5:
            report["recommendations"].append(
                {
                    "category": "query_optimization",
                    "priority": "high",
                    "description": "Multiple slow queries detected",
                    "action": "Review and optimize slow queries, add missing indexes",
                }
            )

        # 基于系统指标的建议
        if system_metrics.get("cpu_usage", {}).get("avg", 0) > 70:
            report["recommendations"].append(
                {
                    "category": "system_optimization",
                    "priority": "medium",
                    "description": "High CPU usage detected",
                    "action": "Consider query optimization or adding read replicas",
                }
            )

        if (
            system_metrics.get("database_size", {}).get("current", 0)
            > 500 * 1024 * 1024
        ):  # 500MB
            report["recommendations"].append(
                {
                    "category": "storage_management",
                    "priority": "medium",
                    "description": "Database size is growing large",
                    "action": "Consider implementing data archiving strategy",
                }
            )

        return report


# 全局实例
query_profiler = QueryProfiler()
db_monitor = DatabaseMonitor()
performance_analyzer = PerformanceAnalyzer()


# SQLAlchemy事件监听器
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    """查询开始前的事件"""
    context._query_start_time = time.time()


@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    """查询完成后的事件"""
    total_time = time.time() - context._query_start_time

    # 记录查询
    try:
        result_count = cursor.rowcount if hasattr(cursor, "rowcount") else None
        query_profiler.record_query(
            sql=statement, duration=total_time, result_count=result_count
        )
    except Exception as e:
        logger.debug(f"Failed to record query metrics: {e}")


@contextmanager
def query_timing(query_name: str):
    """查询计时上下文管理器"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.debug(f"Query '{query_name}' took {duration:.3f}s")


async def start_database_monitoring():
    """启动数据库监控"""
    await db_monitor.start_monitoring(interval=60)
    logger.info("Database monitoring services started")


def stop_database_monitoring():
    """停止数据库监控"""
    db_monitor.stop_monitoring()


def get_performance_dashboard() -> Dict[str, Any]:
    """获取性能仪表板数据"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "query_metrics": {
            "slow_queries": query_profiler.get_slow_queries(5),
            "top_queries": query_profiler.get_top_queries(5),
            "timeline": query_profiler.get_query_timeline(60),
        },
        "system_metrics": db_monitor.get_metrics_summary(hours=1),
        "alerts": db_monitor.get_alerts(),
        "performance_report": performance_analyzer.generate_performance_report(
            query_profiler, db_monitor
        ),
    }


def reset_monitoring_data():
    """重置监控数据"""
    query_profiler.query_history.clear()
    query_profiler.slow_queries.clear()
    query_profiler.query_stats.clear()

    db_monitor.metrics_history.clear()

    logger.info("Monitoring data reset")
