"""
数据库优化套件 - 集成所有优化功能的主模块
提供一键优化、性能监控、配置管理等完整解决方案
"""

from datetime import datetime

import asyncio
import json
from typing import Any, Dict, List, Optional

from repositories.batch_repo import (
    get_batch_processor_stats,
    get_connection_pool_status,
    start_batch_processing,
    stop_batch_processing,
)
from repositories.db_index_optimizer import (
    get_database_performance_metrics,
    optimize_database_performance,
)
from repositories.db_monitor import (
    get_performance_dashboard,
    reset_monitoring_data,
    start_database_monitoring,
    stop_database_monitoring,
)
from repositories.db_sharding import (
    get_sharding_statistics,
    setup_database_sharding,
)
from core.logging import get_logger
from repositories.query_optimizer import (
    get_query_performance_stats,
    start_query_optimization,
    stop_query_optimization,
)

logger = get_logger(__name__)


class DatabaseOptimizationSuite:
    """数据库优化套件"""

    def __init__(self):
        self.is_initialized = False
        self.optimization_config = {
            "enable_query_cache": True,
            "enable_monitoring": True,
            "enable_sharding": True,
            "enable_batch_processing": True,
            "enable_index_optimization": True,
            "auto_optimize": True,
        }

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """初始化优化套件"""
        if self.is_initialized:
            logger.warning("Database optimization suite already initialized")
            return

        if config:
            self.optimization_config.update(config)

        logger.info("Initializing Database Optimization Suite...")

        try:
            # 1. 启动查询优化
            if self.optimization_config.get("enable_query_cache", True):
                await start_query_optimization()
                logger.info("✓ Query optimization enabled")

            # 2. 启动性能监控
            if self.optimization_config.get("enable_monitoring", True):
                await start_database_monitoring()
                logger.info("✓ Performance monitoring enabled")

            # 3. 设置分片和分区
            if self.optimization_config.get("enable_sharding", True):
                sharding_result = setup_database_sharding(enable_partitioning=True)
                logger.info(
                    f"✓ Sharding setup completed: {len(sharding_result.get('partitions_created', []))} partitions"
                )

            # 4. 启动批量处理
            if self.optimization_config.get("enable_batch_processing", True):
                await start_batch_processing()
                logger.info("✓ Batch processing enabled")

            # 5. 索引优化
            if self.optimization_config.get("enable_index_optimization", True):
                if self.optimization_config.get("auto_optimize", True):
                    index_result = optimize_database_performance(apply_changes=True)
                    created_indexes = len(index_result.get("changes_applied", []))
                    logger.info(
                        f"✓ Database optimization completed: {created_indexes} changes applied"
                    )
                else:
                    logger.info("✓ Index optimization configured (manual mode)")

            self.is_initialized = True
            logger.info("🚀 Database Optimization Suite initialized successfully!")

        except Exception as e:
            logger.error(f"Failed to initialize Database Optimization Suite: {e}")
            raise

    async def shutdown(self):
        """关闭优化套件"""
        if not self.is_initialized:
            return

        logger.info("Shutting down Database Optimization Suite...")

        try:
            # 停止各种服务
            if self.optimization_config.get("enable_query_cache", True):
                await stop_query_optimization()
            await stop_database_monitoring()
            await stop_batch_processing()

            self.is_initialized = False
            logger.info("Database Optimization Suite shutdown completed")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def get_comprehensive_status(self) -> Dict[str, Any]:
        """获取全面的状态信息"""
        if not self.is_initialized:
            return {"status": "not_initialized"}

        try:
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "suite_status": "active",
                "config": self.optimization_config,
                "components": {},
            }

            # 查询优化状态
            if self.optimization_config.get("enable_query_cache"):
                try:
                    query_stats = get_query_performance_stats()
                    status["components"]["query_optimization"] = {
                        "status": "active",
                        "stats": query_stats,
                    }
                except Exception as e:
                    status["components"]["query_optimization"] = {
                        "status": "error",
                        "error": str(e),
                    }

            # 监控状态
            if self.optimization_config.get("enable_monitoring"):
                try:
                    monitoring_data = get_performance_dashboard()
                    status["components"]["monitoring"] = {
                        "status": "active",
                        "dashboard": monitoring_data,
                    }
                except Exception as e:
                    status["components"]["monitoring"] = {
                        "status": "error",
                        "error": str(e),
                    }

            # 分片状态
            if self.optimization_config.get("enable_sharding"):
                try:
                    sharding_stats = get_sharding_statistics()
                    status["components"]["sharding"] = {
                        "status": "active",
                        "statistics": sharding_stats,
                    }
                except Exception as e:
                    status["components"]["sharding"] = {
                        "status": "error",
                        "error": str(e),
                    }

            # 批量处理状态
            if self.optimization_config.get("enable_batch_processing"):
                try:
                    batch_stats = get_batch_processor_stats()
                    pool_status = get_connection_pool_status()
                    status["components"]["batch_processing"] = {
                        "status": "active",
                        "batch_stats": batch_stats,
                        "pool_status": pool_status,
                    }
                except Exception as e:
                    status["components"]["batch_processing"] = {
                        "status": "error",
                        "error": str(e),
                    }

            # 数据库性能指标
            try:
                db_metrics = get_database_performance_metrics()
                status["database_metrics"] = db_metrics
            except Exception as e:
                status["database_metrics"] = {"error": str(e)}

            return status

        except Exception as e:
            logger.error(f"Failed to get comprehensive status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """获取优化建议"""
        recommendations = []

        try:
            # 基于当前状态分析
            status = self.get_comprehensive_status()

            # 查询优化建议
            if "query_optimization" in status.get("components", {}):
                query_component = status["components"]["query_optimization"]
                if query_component.get("status") == "active":
                    hot_queries = query_component.get("stats", {}).get(
                        "hot_queries", []
                    )
                    if len(hot_queries) > 5:
                        recommendations.append(
                            {
                                "category": "query_optimization",
                                "priority": "high",
                                "title": "热点查询优化",
                                "description": f"检测到 {len(hot_queries)} 个热点查询，建议进一步优化",
                                "action": "检查查询缓存配置，考虑添加专门的索引",
                            }
                        )

            # 监控建议
            if "monitoring" in status.get("components", {}):
                monitoring_component = status["components"]["monitoring"]
                if monitoring_component.get("status") == "active":
                    alerts = monitoring_component.get("dashboard", {}).get("alerts", [])
                    if alerts:
                        for alert in alerts:
                            recommendations.append(
                                {
                                    "category": "performance_alert",
                                    "priority": alert.get("severity", "medium"),
                                    "title": f'性能告警: {alert.get("type", "unknown")}',
                                    "description": alert.get("message", ""),
                                    "action": "检查系统资源使用情况，考虑扩容或优化",
                                }
                            )

            # 数据库大小建议
            db_metrics = status.get("database_metrics", {})
            if "db_size" in db_metrics:
                db_size_mb = db_metrics["db_size"] / (1024 * 1024)
                if db_size_mb > 500:  # 500MB
                    recommendations.append(
                        {
                            "category": "storage_optimization",
                            "priority": "medium",
                            "title": "数据库大小优化",
                            "description": f"数据库大小已达到 {db_size_mb:.1f}MB",
                            "action": "考虑启用数据归档，清理过期数据",
                        }
                    )

            # 连接池建议
            if "batch_processing" in status.get("components", {}):
                batch_component = status["components"]["batch_processing"]
                if batch_component.get("status") == "active":
                    pool_status = batch_component.get("pool_status", {})
                    checked_out = pool_status.get("checked_out", 0)
                    pool_size = pool_status.get("pool_size", 0)

                    if isinstance(checked_out, int) and isinstance(pool_size, int):
                        if checked_out > pool_size * 0.8:  # 80%以上使用率
                            recommendations.append(
                                {
                                    "category": "connection_pool",
                                    "priority": "medium",
                                    "title": "连接池优化",
                                    "description": f"连接池使用率较高 ({checked_out}/{pool_size})",
                                    "action": "考虑增加连接池大小或优化连接使用",
                                }
                            )

            # 通用建议
            if not recommendations:
                recommendations.append(
                    {
                        "category": "general",
                        "priority": "low",
                        "title": "系统运行良好",
                        "description": "当前数据库性能状态良好，建议定期检查",
                        "action": "继续监控性能指标，定期维护",
                    }
                )

        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            recommendations.append(
                {
                    "category": "error",
                    "priority": "high",
                    "title": "无法生成建议",
                    "description": f"生成优化建议时出错: {str(e)}",
                    "action": "检查系统状态和日志",
                }
            )

        return recommendations

    async def run_optimization_check(self) -> Dict[str, Any]:
        """运行优化检查"""
        logger.info("Running database optimization check...")

        check_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed",
            "checks": {},
            "recommendations": [],
            "actions_taken": [],
        }

        try:
            # 1. 性能指标检查
            db_metrics = get_database_performance_metrics()
            check_result["checks"]["performance_metrics"] = {
                "status": "passed" if db_metrics else "failed",
                "metrics": db_metrics,
            }

            # 2. 查询性能检查
            query_stats = get_query_performance_stats()
            slow_queries = query_stats.get("slow_queries", [])
            check_result["checks"]["query_performance"] = {
                "status": "warning" if len(slow_queries) > 5 else "passed",
                "slow_query_count": len(slow_queries),
                "details": slow_queries[:3],  # 显示前3个
            }

            # 3. 连接池检查
            pool_status = get_connection_pool_status()
            check_result["checks"]["connection_pool"] = {
                "status": "passed",
                "pool_status": pool_status,
            }

            # 4. 批量处理检查
            batch_stats = get_batch_processor_stats()
            check_result["checks"]["batch_processing"] = {
                "status": "passed" if batch_stats.get("is_running") else "warning",
                "stats": batch_stats,
            }

            # 生成建议
            check_result["recommendations"] = self.get_optimization_recommendations()

            # 自动执行某些优化（如果启用）
            if self.optimization_config.get("auto_optimize", True):
                actions = await self._auto_optimize()
                check_result["actions_taken"] = actions

            logger.info("Database optimization check completed")

        except Exception as e:
            logger.error(f"Optimization check failed: {e}")
            check_result["status"] = "failed"
            check_result["error"] = str(e)

        return check_result

    async def _auto_optimize(self) -> List[str]:
        """自动优化操作"""
        actions = []

        try:
            # 清理过期监控数据
            reset_monitoring_data()
            actions.append("清理过期监控数据")

            # 刷新查询缓存统计
            # 这里可以添加更多自动优化逻辑

        except Exception as e:
            logger.error(f"Auto optimization failed: {e}")
            actions.append(f"自动优化失败: {str(e)}")

        return actions

    def save_optimization_report(
        self, report: Dict[str, Any], filename: Optional[str] = None
    ) -> str:
        """保存优化报告"""
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"db_optimization_report_{timestamp}.json"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Optimization report saved to {filename}")
            return filename

        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            raise


# 全局实例
db_optimization_suite = DatabaseOptimizationSuite()


# 便捷函数
async def initialize_database_optimization(config: Optional[Dict[str, Any]] = None):
    """初始化数据库优化"""
    await db_optimization_suite.initialize(config)


async def shutdown_database_optimization():
    """关闭数据库优化"""
    await db_optimization_suite.shutdown()


def get_database_optimization_status() -> Dict[str, Any]:
    """获取数据库优化状态"""
    return db_optimization_suite.get_comprehensive_status()


async def run_database_optimization_check() -> Dict[str, Any]:
    """运行数据库优化检查"""
    return await db_optimization_suite.run_optimization_check()


def get_database_optimization_recommendations() -> List[Dict[str, Any]]:
    """获取数据库优化建议"""
    return db_optimization_suite.get_optimization_recommendations()


# 使用示例
async def main():
    """使用示例"""
    try:
        # 初始化优化套件
        await initialize_database_optimization(
            {
                "enable_query_cache": True,
                "enable_monitoring": True,
                "enable_sharding": True,
                "enable_batch_processing": True,
                "enable_index_optimization": True,
                "auto_optimize": True,
            }
        )

        # 运行优化检查
        check_result = await run_database_optimization_check()
        print(
            "优化检查结果:",
            json.dumps(check_result, indent=2, ensure_ascii=False, default=str),
        )

        # 获取状态
        status = get_database_optimization_status()
        print(
            "当前状态:", json.dumps(status, indent=2, ensure_ascii=False, default=str)
        )

        # 获取建议
        recommendations = get_database_optimization_recommendations()
        print(
            "优化建议:",
            json.dumps(recommendations, indent=2, ensure_ascii=False, default=str),
        )

    except KeyboardInterrupt:
        print("正在关闭...")
    finally:
        await shutdown_database_optimization()


if __name__ == "__main__":
    asyncio.run(main())
