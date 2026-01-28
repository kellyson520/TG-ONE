"""
数据库索引优化器
自动分析查询模式并创建最优索引策略
"""

import os
from sqlalchemy import inspect, text
from typing import Any, Dict, List

from core.db_factory import get_engine
from core.logging import get_logger

logger = get_logger(__name__)


class DatabaseIndexOptimizer:
    """数据库索引优化器"""

    def __init__(self):
        self.engine = get_engine()

    def analyze_query_patterns(self) -> Dict[str, Any]:
        """分析查询模式"""
        try:
            with self.engine.connect() as conn:
                # SQLite查询统计分析
                stats = {}

                # 检查现有索引
                existing_indexes = self._get_existing_indexes()
                stats["existing_indexes"] = existing_indexes

                # 分析表大小
                table_sizes = self._analyze_table_sizes()
                stats["table_sizes"] = table_sizes

                # 模拟常用查询性能
                query_performance = self._analyze_query_performance()
                stats["query_performance"] = query_performance

                return stats
        except Exception as e:
            logger.error(f"Failed to analyze query patterns: {e}")
            return {}

    def _get_existing_indexes(self) -> Dict[str, List[str]]:
        """获取现有索引"""
        try:
            inspector = inspect(self.engine)
            indexes = {}

            for table_name in inspector.get_table_names():
                table_indexes = inspector.get_indexes(table_name)
                indexes[table_name] = [
                    {
                        "name": idx["name"],
                        "columns": idx["column_names"],
                        "unique": idx["unique"],
                    }
                    for idx in table_indexes
                ]

            return indexes
        except Exception as e:
            logger.error(f"Failed to get existing indexes: {e}")
            return {}

    def _analyze_table_sizes(self) -> Dict[str, int]:
        """分析表大小"""
        try:
            with self.engine.connect() as conn:
                # 获取表行数统计
                tables = [
                    "chats",
                    "forward_rules",
                    "keywords",
                    "replace_rules",
                    "media_signatures",
                    "users",
                    "rss_configs",
                    "rss_patterns",
                    "chat_statistics",
                    "rule_statistics",
                    "error_logs",
                    "task_queue",
                ]

                sizes = {}
                for table in tables:
                    try:
                        result = conn.execute(
                            text(f"SELECT COUNT(*) FROM {table}")
                        ).fetchone()
                        sizes[table] = result[0] if result else 0
                    except Exception:
                        sizes[table] = 0

                return sizes
        except Exception as e:
            logger.error(f"Failed to analyze table sizes: {e}")
            return {}

    def _analyze_query_performance(self) -> Dict[str, float]:
        """分析查询性能"""
        test_queries = {
            "rule_by_id": "SELECT * FROM forward_rules WHERE id = 1",
            "keywords_by_rule": "SELECT * FROM keywords WHERE rule_id = 1",
            "media_by_chat_signature": "SELECT * FROM media_signatures WHERE chat_id = 'test' AND signature = 'photo:123'",
            "chat_by_telegram_id": "SELECT * FROM chats WHERE telegram_chat_id = 'test'",
            "active_rules": "SELECT * FROM forward_rules WHERE enable_rule = 1",
            "recent_errors": "SELECT * FROM error_logs WHERE created_at > '2024-01-01' ORDER BY created_at DESC LIMIT 10",
            "rule_join_chat": """
                SELECT r.*, sc.name as source_name, tc.name as target_name 
                FROM forward_rules r 
                JOIN chats sc ON r.source_chat_id = sc.id 
                JOIN chats tc ON r.target_chat_id = tc.id 
                WHERE r.enable_rule = 1 LIMIT 5
            """,
        }

        performance = {}
        try:
            with self.engine.connect() as conn:
                for query_name, sql in test_queries.items():
                    try:
                        import time

                        start_time = time.time()
                        conn.execute(text(sql))
                        end_time = time.time()
                        performance[query_name] = (end_time - start_time) * 1000  # ms
                    except Exception:
                        performance[query_name] = -1  # 查询失败
        except Exception as e:
            logger.error(f"Failed to analyze query performance: {e}")

        return performance

    def create_optimized_indexes(self, force: bool = False) -> List[str]:
        """创建优化索引"""
        created_indexes = []

        # 推荐的复合索引
        recommended_indexes = [
            # ForwardRule常用查询组合
            (
                "forward_rules",
                ["source_chat_id", "enable_rule"],
                "idx_fr_source_enabled",
            ),
            (
                "forward_rules",
                ["target_chat_id", "enable_rule"],
                "idx_fr_target_enabled",
            ),
            ("forward_rules", ["enable_rule", "created_at"], "idx_fr_enabled_created"),
            # Keywords按规则和类型查询
            ("keywords", ["rule_id", "is_blacklist"], "idx_kw_rule_blacklist"),
            ("keywords", ["rule_id", "is_regex"], "idx_kw_rule_regex"),
            ("keywords", ["rule_id", "is_blacklist", "is_regex"], "idx_kw_rule_type"),
            # MediaSignature高频查询
            ("media_signatures", ["chat_id", "file_id"], "idx_ms_chat_fileid"),
            ("media_signatures", ["chat_id", "content_hash"], "idx_ms_chat_hash"),
            ("media_signatures", ["chat_id", "created_at"], "idx_ms_chat_created"),
            ("media_signatures", ["signature", "chat_id"], "idx_ms_sig_chat"),
            # ReplaceRule查询优化
            ("replace_rules", ["rule_id", "pattern"], "idx_rr_rule_pattern"),
            # 统计表时间范围查询
            ("chat_statistics", ["chat_id", "date"], "idx_cs_chat_date"),
            ("rule_statistics", ["rule_id", "date"], "idx_rs_rule_date"),
            # 错误日志查询
            ("error_logs", ["level", "created_at"], "idx_el_level_created"),
            ("error_logs", ["module", "created_at"], "idx_el_module_created"),
            # 任务队列状态查询
            ("task_queue", ["status", "priority"], "idx_tq_status_priority"),
            ("task_queue", ["task_type", "status"], "idx_tq_type_status"),
            ("task_queue", ["scheduled_at", "status"], "idx_tq_scheduled_status"),
            # RSS相关查询
            ("rss_configs", ["rule_id", "enable_rss"], "idx_rc_rule_enabled"),
            ("rss_patterns", ["rss_config_id", "priority"], "idx_rp_config_priority"),
            # 规则同步查询
            ("rule_syncs", ["rule_id", "sync_rule_id"], "idx_rsync_rules"),
            # 推送配置查询
            ("push_configs", ["rule_id", "enable_push_channel"], "idx_pc_rule_enabled"),
        ]

        try:
            # 使用事务上下文，自动提交DDL，避免手动commit导致兼容性问题
            with self.engine.begin() as conn:
                # 检查现有索引
                existing = self._get_existing_index_names()

                for table_name, columns, index_name in recommended_indexes:
                    if index_name not in existing or force:
                        try:
                            # 检查表是否存在
                            table_exists = conn.execute(
                                text(
                                    "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
                                ),
                                {"name": table_name},
                            ).fetchone()

                            if not table_exists:
                                logger.warning(
                                    f"Table {table_name} does not exist, skipping index {index_name}"
                                )
                                continue

                            # 检查列是否存在
                            columns_info = conn.execute(
                                text(f"PRAGMA table_info({table_name})")
                            ).fetchall()
                            existing_columns = {col[1] for col in columns_info}

                            if not all(col in existing_columns for col in columns):
                                logger.warning(
                                    f"Some columns {columns} do not exist in {table_name}, skipping index {index_name}"
                                )
                                continue

                            # 创建索引
                            columns_str = ", ".join(columns)
                            create_sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
                            conn.execute(text(create_sql))

                            created_indexes.append(index_name)
                            logger.info(
                                f"Created index: {index_name} on {table_name}({columns_str})"
                            )

                        except Exception as e:
                            logger.error(f"Failed to create index {index_name}: {e}")
                            continue

        except Exception as e:
            logger.error(f"Failed to create optimized indexes: {e}")

        return created_indexes

    def _get_existing_index_names(self) -> set:
        """获取现有索引名称"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
                    )
                ).fetchall()
                return {row[0] for row in result}
        except Exception as e:
            logger.error(f"Failed to get existing index names: {e}")
            return set()

    def analyze_slow_queries(self) -> List[Dict[str, Any]]:
        """分析慢查询（模拟）"""
        # 在生产环境中，这里可以接入真实的慢查询日志
        potential_slow_queries = [
            {
                "query_type": "large_table_scan",
                "description": "Full table scan on media_signatures",
                "recommendation": "Add indexes on chat_id, signature, file_id",
                "impact": "high",
            },
            {
                "query_type": "complex_join",
                "description": "Join between forward_rules and multiple related tables",
                "recommendation": "Use query optimization and preloading",
                "impact": "medium",
            },
            {
                "query_type": "range_query",
                "description": "Date range queries on statistics tables",
                "recommendation": "Add composite indexes on (entity_id, date)",
                "impact": "medium",
            },
        ]

        return potential_slow_queries

    def optimize_database_settings(self) -> Dict[str, Any]:
        """优化数据库设置"""
        optimizations = []

        try:
            with self.engine.connect() as conn:
                # 检查当前设置
                current_settings = {}

                # WAL模式检查
                wal_mode = conn.execute(text("PRAGMA journal_mode")).fetchone()
                current_settings["journal_mode"] = (
                    wal_mode[0] if wal_mode else "unknown"
                )

                # 同步模式检查
                sync_mode = conn.execute(text("PRAGMA synchronous")).fetchone()
                current_settings["synchronous"] = (
                    sync_mode[0] if sync_mode else "unknown"
                )

                # 缓存大小检查
                cache_size = conn.execute(text("PRAGMA cache_size")).fetchone()
                current_settings["cache_size"] = (
                    cache_size[0] if cache_size else "unknown"
                )

                # 优化建议
                if current_settings.get("journal_mode") != "wal":
                    optimizations.append(
                        {
                            "setting": "journal_mode",
                            "current": current_settings.get("journal_mode"),
                            "recommended": "WAL",
                            "command": "PRAGMA journal_mode=WAL",
                            "benefit": "提高并发读写性能",
                        }
                    )

                if current_settings.get("synchronous", 0) > 1:
                    optimizations.append(
                        {
                            "setting": "synchronous",
                            "current": current_settings.get("synchronous"),
                            "recommended": "NORMAL",
                            "command": "PRAGMA synchronous=NORMAL",
                            "benefit": "在安全和性能间平衡",
                        }
                    )

                if abs(current_settings.get("cache_size", 0)) < 10000:
                    optimizations.append(
                        {
                            "setting": "cache_size",
                            "current": current_settings.get("cache_size"),
                            "recommended": "-64000",  # 64MB
                            "command": "PRAGMA cache_size=-64000",
                            "benefit": "增加内存缓存，减少磁盘I/O",
                        }
                    )

                return {
                    "current_settings": current_settings,
                    "optimizations": optimizations,
                }

        except Exception as e:
            logger.error(f"Failed to optimize database settings: {e}")
            return {"current_settings": {}, "optimizations": []}

    def apply_database_optimizations(self) -> List[str]:
        """应用数据库优化"""
        applied = []

        try:
            with self.engine.connect() as conn:
                optimizations = [
                    ("PRAGMA journal_mode=WAL", "启用WAL模式"),
                    ("PRAGMA synchronous=NORMAL", "设置同步模式为NORMAL"),
                    ("PRAGMA cache_size=-64000", "设置缓存大小为64MB"),
                    ("PRAGMA temp_store=MEMORY", "临时数据存储在内存"),
                    ("PRAGMA mmap_size=268435456", "启用内存映射，256MB"),
                    ("PRAGMA optimize", "优化查询计划器统计"),
                ]

                for pragma_sql, description in optimizations:
                    try:
                        conn.execute(text(pragma_sql))
                        applied.append(f"{description}: {pragma_sql}")
                        logger.info(f"Applied optimization: {description}")
                    except Exception as e:
                        logger.error(f"Failed to apply optimization {pragma_sql}: {e}")

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to apply database optimizations: {e}")

        return applied

    def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        return {
            "query_patterns": self.analyze_query_patterns(),
            "slow_queries": self.analyze_slow_queries(),
            "database_settings": self.optimize_database_settings(),
            "recommendations": self._get_optimization_recommendations(),
        }

    def _get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """获取优化建议"""
        recommendations = [
            {
                "category": "indexes",
                "priority": "high",
                "description": "为高频查询创建复合索引",
                "action": "运行 create_optimized_indexes()",
                "expected_improvement": "查询性能提升 50-80%",
            },
            {
                "category": "caching",
                "priority": "high",
                "description": "启用查询结果缓存",
                "action": "使用 @cached_query 装饰器",
                "expected_improvement": "热点查询性能提升 90%+",
            },
            {
                "category": "batch_operations",
                "priority": "medium",
                "description": "使用批量操作替代逐条处理",
                "action": "使用 BatchQueryExecutor",
                "expected_improvement": "批量操作性能提升 300-500%",
            },
            {
                "category": "read_write_separation",
                "priority": "medium",
                "description": "读查询使用只读会话",
                "action": "使用 get_read_session()",
                "expected_improvement": "减少主库压力，提升并发能力",
            },
            {
                "category": "connection_pooling",
                "priority": "low",
                "description": "优化连接池配置",
                "action": "调整 DB_POOL_SIZE 和 DB_MAX_OVERFLOW",
                "expected_improvement": "提升并发处理能力",
            },
        ]

        return recommendations


# 全局实例
db_optimizer = DatabaseIndexOptimizer()


def optimize_database_performance(apply_changes: bool = False) -> Dict[str, Any]:
    """一键优化数据库性能"""
    logger.info("Starting database performance optimization...")

    results = {
        "analysis": db_optimizer.get_optimization_report(),
        "changes_applied": [],
    }

    if apply_changes:
        # 创建索引
        created_indexes = db_optimizer.create_optimized_indexes()
        results["changes_applied"].extend(
            [f"Created index: {idx}" for idx in created_indexes]
        )

        # 应用数据库设置优化
        applied_optimizations = db_optimizer.apply_database_optimizations()
        results["changes_applied"].extend(applied_optimizations)

    logger.info(
        f"Database optimization completed. Applied {len(results['changes_applied'])} changes."
    )
    return results


def get_database_performance_metrics() -> Dict[str, Any]:
    """获取数据库性能指标"""
    try:
        with get_engine().connect() as conn:
            metrics = {}

            # 基本统计
            metrics["db_size"] = conn.execute(
                text(
                    "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
                )
            ).fetchone()[0]

            # WAL文件大小
            wal_size = 0
            from pathlib import Path

            wal_file = (
                Path(__file__).resolve().parent.parent / "db" / "forward.db-wal"
            ).resolve()
            if wal_file.exists():
                wal_size = os.path.getsize(str(wal_file))
            metrics["wal_size"] = wal_size

            # 表统计
            table_stats = db_optimizer._analyze_table_sizes()
            metrics["table_row_counts"] = table_stats

            # 索引统计
            indexes = db_optimizer._get_existing_indexes()
            metrics["index_count"] = sum(
                len(table_indexes) for table_indexes in indexes.values()
            )

            # 查询性能
            query_performance = db_optimizer._analyze_query_performance()
            metrics["query_performance_ms"] = query_performance

            return metrics

    except Exception as e:
        logger.error(f"Failed to get database performance metrics: {e}")
        return {}
