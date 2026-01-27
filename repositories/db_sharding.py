"""
数据分片和分区策略
支持水平扩展和数据分离，提升查询性能和存储效率
"""

import hashlib
from datetime import datetime, timedelta

import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import Any, Callable, Dict, List, Optional, Union

from models.models import get_engine, get_session
from core.logging import get_logger

logger = get_logger(__name__)


class ShardingStrategy:
    """分片策略基类"""

    def get_shard_key(self, **kwargs) -> str:
        """获取分片键"""
        raise NotImplementedError

    def get_shard_id(self, shard_key: str) -> int:
        """根据分片键获取分片ID"""
        raise NotImplementedError


class ChatIdSharding(ShardingStrategy):
    """基于聊天ID的分片策略"""

    def __init__(self, num_shards: int = 16):
        self.num_shards = num_shards

    def get_shard_key(self, chat_id: Union[str, int], **kwargs) -> str:
        """获取聊天ID分片键"""
        return str(chat_id)

    def get_shard_id(self, shard_key: str) -> int:
        """基于聊天ID计算分片"""
        hash_value = int(hashlib.md5(shard_key.encode()).hexdigest()[:8], 16)
        return hash_value % self.num_shards


class UserIdSharding(ShardingStrategy):
    """基于用户ID的分片策略"""

    def __init__(self, num_shards: int = 8):
        self.num_shards = num_shards

    def get_shard_key(self, user_id: Union[str, int], **kwargs) -> str:
        """获取用户ID分片键"""
        return str(user_id)

    def get_shard_id(self, shard_key: str) -> int:
        """基于用户ID计算分片"""
        hash_value = int(hashlib.md5(shard_key.encode()).hexdigest()[:8], 16)
        return hash_value % self.num_shards


class TimeBasedPartitioning:
    """基于时间的分区策略"""

    def __init__(self, partition_type: str = "daily"):
        """
        Args:
            partition_type: 分区类型 ('daily', 'weekly', 'monthly')
        """
        self.partition_type = partition_type

    def get_partition_key(self, timestamp: Union[str, datetime]) -> str:
        """获取分区键"""
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.utcnow()
        else:
            dt = timestamp

        if self.partition_type == "daily":
            return dt.strftime("%Y%m%d")
        elif self.partition_type == "weekly":
            year, week, _ = dt.isocalendar()
            return f"{year}W{week:02d}"
        elif self.partition_type == "monthly":
            return dt.strftime("%Y%m")
        else:
            return dt.strftime("%Y%m%d")

    def get_partition_range(self, partition_key: str) -> tuple:
        """获取分区时间范围"""
        if self.partition_type == "daily":
            dt = datetime.strptime(partition_key, "%Y%m%d")
            start = dt
            end = dt + timedelta(days=1)
        elif self.partition_type == "weekly":
            year = int(partition_key[:4])
            week = int(partition_key[5:])
            dt = datetime.strptime(f"{year}-W{week:02d}-1", "%Y-W%U-%w")
            start = dt
            end = dt + timedelta(weeks=1)
        elif self.partition_type == "monthly":
            dt = datetime.strptime(partition_key, "%Y%m")
            start = dt
            if dt.month == 12:
                end = dt.replace(year=dt.year + 1, month=1)
            else:
                end = dt.replace(month=dt.month + 1)
        else:
            dt = datetime.strptime(partition_key, "%Y%m%d")
            start = dt
            end = dt + timedelta(days=1)

        return start, end


class DataShardingManager:
    """数据分片管理器"""

    def __init__(self):
        self.strategies = {
            "chat_id": ChatIdSharding(),
            "user_id": UserIdSharding(),
        }
        self.time_partitioner = TimeBasedPartitioning("daily")

    def get_media_signature_shard(self, chat_id: str) -> int:
        """获取媒体签名分片"""
        strategy = self.strategies["chat_id"]
        shard_key = strategy.get_shard_key(chat_id=chat_id)
        return strategy.get_shard_id(shard_key)

    def get_error_log_partition(self, timestamp: Union[str, datetime]) -> str:
        """获取错误日志分区"""
        return self.time_partitioner.get_partition_key(timestamp)

    def get_statistics_partition(self, date: Union[str, datetime]) -> str:
        """获取统计数据分区"""
        return self.time_partitioner.get_partition_key(date)

    def should_archive_partition(
        self, partition_key: str, retention_days: int = 30
    ) -> bool:
        """判断分区是否应该归档"""
        try:
            start_time, _ = self.time_partitioner.get_partition_range(partition_key)
            cutoff = datetime.utcnow() - timedelta(days=retention_days)
            return start_time < cutoff
        except Exception:
            return False


class VirtualTableManager:
    """虚拟表管理器（用于查询路由）"""

    def __init__(self):
        self.sharding_manager = DataShardingManager()

    def route_media_signature_query(self, chat_id: str, **conditions) -> Dict[str, Any]:
        """路由媒体签名查询"""
        shard_id = self.sharding_manager.get_media_signature_shard(chat_id)

        # 在单数据库环境中，我们使用逻辑分片（添加shard_id条件）
        query_info = {
            "table": "media_signatures",
            "shard_id": shard_id,
            "conditions": {**conditions, "chat_id": chat_id},
            "optimization_hint": f"shard_{shard_id}",
        }

        return query_info

    def route_error_log_query(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """路由错误日志查询"""
        partitions = []
        current = start_date

        while current <= end_date:
            partition_key = self.sharding_manager.get_error_log_partition(current)
            partitions.append(
                {
                    "table": "error_logs",
                    "partition_key": partition_key,
                    "date_range": (current, min(current + timedelta(days=1), end_date)),
                }
            )
            current += timedelta(days=1)

        return partitions

    def get_optimized_query_plan(
        self, table: str, conditions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """获取优化的查询计划"""
        plan = {"table": table, "conditions": conditions, "optimizations": []}

        # 根据表类型添加优化建议
        if table == "media_signatures" and "chat_id" in conditions:
            chat_id = conditions["chat_id"]
            shard_info = self.route_media_signature_query(chat_id, **conditions)
            plan["shard_hint"] = shard_info["optimization_hint"]
            plan["optimizations"].append("shard_routing")

        if table in ["error_logs", "chat_statistics", "rule_statistics"]:
            if "created_at" in conditions or "date" in conditions:
                plan["optimizations"].append("time_partition_pruning")

        # 添加索引使用建议
        if table == "forward_rules":
            if "source_chat_id" in conditions and "enable_rule" in conditions:
                plan["suggested_index"] = "idx_fr_source_enabled"
            elif "target_chat_id" in conditions and "enable_rule" in conditions:
                plan["suggested_index"] = "idx_fr_target_enabled"

        if table == "keywords":
            if "rule_id" in conditions:
                if "is_blacklist" in conditions:
                    plan["suggested_index"] = "idx_kw_rule_blacklist"
                elif "is_regex" in conditions:
                    plan["suggested_index"] = "idx_kw_rule_regex"
                else:
                    plan["suggested_index"] = "idx_kw_rule_type"

        return plan


class QueryDistributor:
    """查询分发器"""

    def __init__(self):
        self.virtual_table_manager = VirtualTableManager()

    def execute_distributed_query(
        self,
        table: str,
        conditions: Dict[str, Any],
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """执行分布式查询"""
        plan = self.virtual_table_manager.get_optimized_query_plan(table, conditions)

        try:
            with get_session() as session:
                # 构建查询
                query_parts = []
                params = {}

                # 添加基本条件
                for field, value in conditions.items():
                    if value is not None:
                        query_parts.append(f"{field} = :{field}")
                        params[field] = value

                where_clause = " AND ".join(query_parts) if query_parts else "1=1"

                # 构建完整查询
                sql = f"SELECT * FROM {table} WHERE {where_clause}"

                if order_by:
                    sql += f" ORDER BY {order_by}"

                if limit:
                    sql += f" LIMIT {limit}"

                # 添加查询提示（SQLite中通过注释形式）
                if "shard_hint" in plan:
                    sql = f"/* SHARD_HINT: {plan['shard_hint']} */ {sql}"

                if "suggested_index" in plan:
                    sql = f"/* USE_INDEX: {plan['suggested_index']} */ {sql}"

                logger.debug(f"Executing optimized query: {sql}")
                logger.debug(f"Query plan: {plan}")

                result = session.execute(text(sql), params)

                # 转换结果为字典列表
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Distributed query failed: {e}")
            return []

    def execute_aggregation_query(
        self,
        table: str,
        agg_func: str,
        group_by: Optional[str] = None,
        conditions: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """执行聚合查询"""
        conditions = conditions or {}

        try:
            with get_session() as session:
                # 构建聚合查询
                select_parts = [f"{agg_func} as agg_result"]
                if group_by:
                    select_parts.insert(0, group_by)

                select_clause = ", ".join(select_parts)

                # 构建条件
                query_parts = []
                params = {}

                for field, value in conditions.items():
                    if value is not None:
                        query_parts.append(f"{field} = :{field}")
                        params[field] = value

                where_clause = " AND ".join(query_parts) if query_parts else "1=1"

                # 构建完整查询
                sql = f"SELECT {select_clause} FROM {table} WHERE {where_clause}"

                if group_by:
                    sql += f" GROUP BY {group_by}"

                logger.debug(f"Executing aggregation query: {sql}")

                result = session.execute(text(sql), params)
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Aggregation query failed: {e}")
            return []


class PartitionManager:
    """分区管理器"""

    def __init__(self):
        self.time_partitioner = TimeBasedPartitioning("daily")

    def create_time_partitions(
        self, table: str, start_date: datetime, days: int = 30
    ) -> List[str]:
        """创建时间分区（逻辑分区）"""
        partitions = []

        for i in range(days):
            date = start_date + timedelta(days=i)
            partition_key = self.time_partitioner.get_partition_key(date)

            # 在SQLite中，我们使用视图来模拟分区
            view_name = f"{table}_p_{partition_key}"

            try:
                with get_session() as session:
                    # 创建分区视图
                    start_time, end_time = self.time_partitioner.get_partition_range(
                        partition_key
                    )

                    if table in ["error_logs"]:
                        date_field = "created_at"
                    elif table in ["chat_statistics", "rule_statistics"]:
                        date_field = "date"
                    else:
                        date_field = "created_at"

                    view_sql = f"""
                    CREATE VIEW IF NOT EXISTS {view_name} AS
                    SELECT * FROM {table}
                    WHERE {date_field} >= '{start_time.isoformat()}'
                    AND {date_field} < '{end_time.isoformat()}'
                    """

                    session.execute(text(view_sql))
                    session.commit()

                    partitions.append(view_name)
                    logger.debug(f"Created partition view: {view_name}")

            except Exception as e:
                logger.error(f"Failed to create partition {view_name}: {e}")

        return partitions

    def cleanup_old_partitions(self, table: str, retention_days: int = 90) -> List[str]:
        """清理旧分区"""
        cleaned = []

        try:
            with get_session() as session:
                # 获取所有相关视图
                views_result = session.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='view' AND name LIKE :pattern"
                    ),
                    {"pattern": f"{table}_p_%"},
                )

                for view_row in views_result:
                    view_name = view_row[0]

                    # 提取分区键
                    partition_key = view_name.split("_p_")[-1]

                    # 检查是否应该清理
                    sharding_manager = DataShardingManager()
                    if sharding_manager.should_archive_partition(
                        partition_key, retention_days
                    ):
                        session.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
                        cleaned.append(view_name)
                        logger.info(f"Cleaned up old partition: {view_name}")

                session.commit()

        except Exception as e:
            logger.error(f"Failed to cleanup old partitions: {e}")

        return cleaned

    def get_partition_statistics(self, table: str) -> Dict[str, Any]:
        """获取分区统计信息"""
        stats = {
            "total_partitions": 0,
            "partition_sizes": {},
            "oldest_partition": None,
            "newest_partition": None,
        }

        try:
            with get_session() as session:
                # 获取所有分区视图
                views_result = session.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='view' AND name LIKE :pattern"
                    ),
                    {"pattern": f"{table}_p_%"},
                )

                partition_keys = []
                for view_row in views_result:
                    view_name = view_row[0]
                    partition_key = view_name.split("_p_")[-1]
                    partition_keys.append(partition_key)

                    # 获取分区大小
                    try:
                        size_result = session.execute(
                            text(f"SELECT COUNT(*) FROM {view_name}")
                        )
                        size = size_result.fetchone()[0]
                        stats["partition_sizes"][partition_key] = size
                    except Exception:
                        stats["partition_sizes"][partition_key] = 0

                stats["total_partitions"] = len(partition_keys)

                if partition_keys:
                    sorted_keys = sorted(partition_keys)
                    stats["oldest_partition"] = sorted_keys[0]
                    stats["newest_partition"] = sorted_keys[-1]

        except Exception as e:
            logger.error(f"Failed to get partition statistics: {e}")

        return stats


# 全局实例
sharding_manager = DataShardingManager()
query_distributor = QueryDistributor()
partition_manager = PartitionManager()


def setup_database_sharding(enable_partitioning: bool = True) -> Dict[str, Any]:
    """设置数据库分片和分区"""
    logger.info("Setting up database sharding and partitioning...")

    results = {
        "sharding_enabled": True,
        "partitions_created": [],
        "optimizations_applied": [],
    }

    try:
        if enable_partitioning:
            # 为日志表创建分区
            start_date = datetime.utcnow() - timedelta(days=7)  # 最近7天

            for table in ["error_logs", "chat_statistics", "rule_statistics"]:
                partitions = partition_manager.create_time_partitions(
                    table, start_date, days=14
                )
                results["partitions_created"].extend(partitions)

        # 记录分片策略
        results["sharding_strategies"] = {
            "media_signatures": "chat_id_hash",
            "error_logs": "time_partition",
            "statistics": "time_partition",
        }

        results["optimizations_applied"].append("Virtual table routing enabled")
        results["optimizations_applied"].append("Query plan optimization enabled")

        logger.info(
            f"Database sharding setup completed. Created {len(results['partitions_created'])} partitions."
        )

    except Exception as e:
        logger.error(f"Failed to setup database sharding: {e}")
        results["error"] = str(e)

    return results


def get_sharding_statistics() -> Dict[str, Any]:
    """获取分片统计信息"""
    stats = {}

    try:
        # 媒体签名分片统计
        with get_session() as session:
            shard_stats = {}
            for shard_id in range(16):  # 假设16个分片
                count_result = session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM media_signatures 
                        WHERE abs(cast(substr(chat_id, 1, 8) as integer)) % 16 = :shard_id
                        """
                    ),
                    {"shard_id": shard_id},
                )
                count = count_result.fetchone()[0] if count_result else 0
                shard_stats[f"shard_{shard_id}"] = count

            stats["media_signature_shards"] = shard_stats

        # 分区统计
        for table in ["error_logs", "chat_statistics", "rule_statistics"]:
            partition_stats = partition_manager.get_partition_statistics(table)
            stats[f"{table}_partitions"] = partition_stats

    except Exception as e:
        logger.error(f"Failed to get sharding statistics: {e}")
        stats["error"] = str(e)

    return stats


def optimize_query_with_sharding(
    table: str, conditions: Dict[str, Any], limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """使用分片优化查询"""
    return query_distributor.execute_distributed_query(table, conditions, limit=limit)
