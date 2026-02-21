from datetime import datetime, timedelta
from typing import Type, Any

from sqlalchemy import select, delete, func

from models.models import (
    RuleLog, RuleStatistics, ChatStatistics, 
    ErrorLog, MediaSignature, TaskQueue
)
from repositories.archive_store import write_parquet, compact_small_files
from repositories.archive_init import init_archive_system
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

class ArchiveManager:
    """
    数据归档管理器
    负责主库旧数据的扫描、Parquet序列化、以及主库清理。
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        # 默认归档表及对应的保留天数，优先从 settings 获取
        self.archive_config = {
            RuleLog: getattr(settings, 'HOT_DAYS_LOG', 30),
            RuleStatistics: getattr(settings, 'HOT_DAYS_STATS', 180),
            ChatStatistics: getattr(settings, 'HOT_DAYS_STATS', 180),
            ErrorLog: getattr(settings, 'HOT_DAYS_LOG', 30),
            MediaSignature: getattr(settings, 'HOT_DAYS_SIGN', 365),
            TaskQueue: 7  # 已完成/失败的任务通常不需要保留太久
        }
        # Bloom 索引配置：模型 -> 需要索引的字段
        self.bloom_config = {
            MediaSignature: ['signature', 'content_hash']
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
                time_column < cutoff_date
            )
            result = await session.execute(count_stmt)
            count = result.scalar()
            
            logger.info(f"表 {table_name} 发现 {count} 条待归档记录 (截止日期: {cutoff_date})")
            if count == 0:
                return
            
            logger.info(f"表 {table_name} 发现 {count} 条待归档记录")

            # 分批处理以避免内存爆炸和长时间锁表
            # 使用较小的默认批次以减少 SQLite 锁定时间
            batch_size = getattr(settings, 'ARCHIVE_BATCH_SIZE', 5000)
            
            import asyncio
            from sqlalchemy.exc import OperationalError
            
            for offset in range(0, count, batch_size):
                logger.info(f"正在处理 {table_name} 分块: offset={offset}, batch_size={batch_size}")
                
                # 针对每一块增加重试逻辑，解决 (sqlite3.OperationalError) database is locked
                max_retries = 5
                retry_delay = 1.0  # 初始延迟 1 秒
                
                records = []
                for attempt in range(max_retries):
                    try:
                        stmt = select(model).where(
                            time_column < cutoff_date
                        ).limit(batch_size)
                        
                        res = await session.execute(stmt)
                        records = res.scalars().all()
                        break # 成功获取记录，跳出重试循环
                    except OperationalError as oe:
                        if "locked" in str(oe).lower() and attempt < max_retries - 1:
                            logger.warning(f"获取 {table_name} 记录时遭遇数据库锁定 (尝试 {attempt+1}/{max_retries}): {oe}. 正在重试...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # 指数回退
                        else:
                            raise
                
                logger.info(f"成功获取 {len(records)} 条记录")
                
                if not records:
                    logger.debug(f"分块 offset={offset} 未返回更多记录，停止当前表处理")
                    break
                
                # 转换为字典列表
                rows = []
                for rec in records:
                    row = {c.name: getattr(rec, c.name) for c in model.__table__.columns}
                    rows.append(row)
                
                # 写入 Parquet
                first_rec_time = rows[0].get('created_at') or rows[0].get('timestamp')
                if isinstance(first_rec_time, datetime):
                    partition_dt = first_rec_time
                elif isinstance(first_rec_time, str):
                    try:
                        partition_dt = datetime.fromisoformat(first_rec_time)
                    except ValueError:
                        partition_dt = datetime.utcnow()
                else:
                    partition_dt = datetime.utcnow()
                
                try:
                    write_result = write_parquet(table_name, rows, partition_dt=partition_dt)
                    if not write_result:
                        logger.error(f"归档表 {table_name} 写入 Parquet 失败（返回空路径），跳过删除步骤")
                        continue
                    
                    # 如果有 Bloom 索引配置，更新索引
                    if model in self.bloom_config:
                        from repositories.bloom_index import bloom
                        fields = self.bloom_config[model]
                        bloom.add_batch(table_name, rows, fields)
                        logger.info(f"已同步更新 {table_name} 的 Bloom 索引")

                    # 写入成功后从主库删除，增加重试
                    ids_to_delete = [getattr(rec, 'id') for rec in records]
                    del_stmt = delete(model).where(model.id.in_(ids_to_delete))
                    
                    retry_delay = 1.0 # 重置回退
                    for attempt in range(max_retries):
                        try:
                            await session.execute(del_stmt)
                            await session.commit()
                            logger.info(f"已成功归档并从主库移除 {len(records)} 条 {table_name} 记录")
                            break
                        except OperationalError as oe:
                            await session.rollback() # 失败时回滚
                            if "locked" in str(oe).lower() and attempt < max_retries - 1:
                                logger.warning(f"删除 {table_name} 记录时遭遇数据库锁定 (尝试 {attempt+1}/{max_retries}): {oe}. 正在重试...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                            else:
                                raise
                except Exception as e:
                    await session.rollback()
                    logger.error(f"归档表 {table_name} 分块处理失败: {e}")
                    # 如果是致命错误（非锁定），则中断本表处理
                    if not isinstance(e, OperationalError) or "locked" not in str(e).lower():
                        break

            # 归档后主库空间释放 (注意：VACUUM 不建议在常规事务中运行)
            # logger.info(f"执行表 {table_name} 的空间优化...")
            # await session.execute(text("VACUUM"))

    async def get_combined_logs(self, rule_id: int, limit: int = 100):
        """跨库查询：结合热库 (SQLite) 和冷库 (Parquet)"""
        print(f"DEBUG: Entering get_combined_logs, rule_id={rule_id}, limit={limit}")
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
            from repositories.db_context import async_db_session
            session_factory = async_db_session
        _instance = ArchiveManager(session_factory)
    return _instance
