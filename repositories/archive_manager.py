from datetime import datetime, timedelta
from typing import Type, Any

from sqlalchemy import select, delete, func

from models.models import (
    RuleLog, RuleStatistics, ChatStatistics, 
    ErrorLog, MediaSignature, TaskQueue
)
from repositories.archive_store import write_parquet, compact_small_files
from repositories.archive_init import init_archive_system
from core.logging import get_logger

logger = get_logger(__name__)

class ArchiveManager:
    """
    数据归档管理器
    负责主库旧数据的扫描、Parquet序列化、以及主库清理。
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        # 默认归档表及对应的保留天数
        self.archive_config = {
            RuleLog: 30,
            RuleStatistics: 180,
            ChatStatistics: 180,
            ErrorLog: 30,
            MediaSignature: 365,
            TaskQueue: 7  # 已完成/失败的任务通常不需要保留太久
        }
        # 记录归档任务状态
        self.is_running = False

    async def initialize(self):
        """初始化归档子系统"""
        logger.info("正在初始化归档子系统（创建目录与验证）...")
        return init_archive_system()

    async def run_archiving_cycle(self):
        """执行一个完整的归档周期"""
        if self.is_running:
            logger.warning("归档任务已在运行中，跳过本次周期")
            return
        
        self.is_running = True
        try:
            logger.info("开始执行数据归档周期...")
            for model, days in self.archive_config.items():
                await self.archive_model_data(model, days)
            
            # 执行合并小文件操作（可选）
            for model in self.archive_config.keys():
                table_name = model.__tablename__
                compact_small_files(table_name)
                
            logger.info("数据归档周期执行完成")
        except Exception as e:
            logger.error(f"归档周期执行异常: {e}", exc_info=True)
        finally:
            self.is_running = False

    async def archive_model_data(self, model: Type[Any], days_threshold: int):
        """归档指定模型的数据"""
        table_name = model.__tablename__
        logger.info(f"开始归档表 {table_name}, 阈值: {days_threshold} 天")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)
        
        async with self.session_factory() as session:
            # 找到符合条件的记录（假设所有模型都有 created_at 或 timestamp）
            # 注意：SQLite 中的 created_at 通常是字符串 ISO 格式
            
            time_column = getattr(model, 'created_at', None)
            if time_column is None:
                time_column = getattr(model, 'timestamp', None)
                
            if time_column is None:
                logger.warning(f"表 {table_name} 没有时间列，无法归档")
                return

            # 查询旧数据量
            count_stmt = select(func.count()).select_from(model).where(
                time_column < cutoff_date.isoformat()
            )
            result = await session.execute(count_stmt)
            count = result.scalar()
            
            if count == 0:
                logger.info(f"表 {table_name} 没有需要归档的旧数据")
                return

            logger.info(f"表 {table_name} 发现 {count} 条待归档记录")

            # 分批处理以避免内存爆炸
            batch_size = 50000
            for offset in range(0, count, batch_size):
                stmt = select(model).where(
                    time_column < cutoff_date.isoformat()
                ).limit(batch_size)
                
                res = await session.execute(stmt)
                records = res.scalars().all()
                
                if not records:
                    break
                
                # 转换为字典列表
                rows = []
                for rec in records:
                    row = {c.name: getattr(rec, c.name) for c in model.__table__.columns}
                    # 处理不可序列化对象（如有）
                    rows.append(row)
                
                # 写入 Parquet
                # 选取第一条记录的时间作为分区时间（近似）
                partition_dt = datetime.fromisoformat(rows[0].get('created_at') or rows[0].get('timestamp'))
                try:
                    write_parquet(table_name, rows, partition_dt=partition_dt)
                    
                    # 写入成功后从主库删除
                    ids_to_delete = [getattr(rec, 'id') for rec in records]
                    del_stmt = delete(model).where(model.id.in_(ids_to_delete))
                    await session.execute(del_stmt)
                    await session.commit()
                    
                    logger.info(f"已成功归档并从主库移除 {len(records)} 条 {table_name} 记录")
                except Exception as e:
                    await session.rollback()
                    logger.error(f"归档表 {table_name} 分块失败: {e}")
                    break

            # 归档后主库空间释放 (注意：VACUUM 不建议在常规事务中运行)
            # logger.info(f"执行表 {table_name} 的空间优化...")
            # await session.execute(text("VACUUM"))

    async def get_combined_logs(self, rule_id: int, limit: int = 100):
        """跨库查询：结合热库 (SQLite) 和冷库 (Parquet)"""
        # 1. 查热库
        async with self.session_factory() as session:
            stmt = select(RuleLog).where(RuleLog.rule_id == rule_id).order_by(RuleLog.created_at.desc()).limit(limit)
            res = await session.execute(stmt)
            hot_logs = res.scalars().all()
            
        results = []
        for log in hot_logs:
            results.append({c.name: getattr(log, c.name) for c in RuleLog.__table__.columns})
            
        # 2. 如果热库数据不足 limit，查冷库
        if len(results) < limit:
            from repositories.archive_store import query_parquet_duckdb
            remaining = limit - len(results)
            cold_logs = query_parquet_duckdb(
                table="rule_logs",
                where_sql="rule_id = ?",
                params=[rule_id],
                limit=remaining,
                order_by="created_at DESC"
            )
            results.extend(cold_logs)
            
        return results

# 单例辅助函数
_instance = None

def get_archive_manager(session_factory=None):
    global _instance
    if _instance is None:
        if session_factory is None:
            # 尝试从 db_context 获取或由外部注入
            from repositories.db_context import db_session
            session_factory = db_session
        _instance = ArchiveManager(session_factory)
    return _instance
