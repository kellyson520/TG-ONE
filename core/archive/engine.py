from typing import Type, Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, delete, func
from core.container import container
from repositories.archive_store import write_parquet, model_to_dict
from core.config import settings

logger = logging.getLogger(__name__)

class ArchiveResult:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.archived_count = 0
        self.success = False
        self.error = None
        self.start_time = datetime.now()
        self.end_time = None
        self.physical_size_mb = 0.0

    def to_dict(self):
        return {
            "table_name": self.table_name,
            "archived_count": self.archived_count,
            "success": self.success,
            "error": str(self.error) if self.error else None,
            "duration": (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        }

class UniversalArchiver:
    """通用归档引擎，支持任何带有 created_at 字段的 SQLAlchemy 模型。"""

    def __init__(self):
        self.batch_size = settings.ARCHIVE_BATCH_SIZE

    async def archive_table(
        self,
        model_class: Any,
        hot_days: int,
        batch_size: Optional[int] = None,
        dry_run: bool = False,
        time_column: str = "created_at"
    ) -> ArchiveResult:
        table_name = model_class.__tablename__
        result = ArchiveResult(table_name)
        
        if batch_size:
            self.batch_size = batch_size

        logger.info(f"[UniversalArchiver] 开始归档表 {table_name}, 字段 {time_column}, 保留热数据 {hot_days} 天")
        
        try:
            cutoff_date = datetime.now() - timedelta(days=hot_days)
            
            # 获取模型的时间字段属性
            time_attr = getattr(model_class, time_column)
            
            # 处理时间对比逻辑：如果是 String 类型，则将日期转为字符串对比
            # 注意：这要求数据库存的是 ISO 格式字符串
            from sqlalchemy import String as SQLA_String
            is_string_time = False
            try:
                # 尝试检查列类型是否为 String
                if isinstance(time_attr.property.columns[0].type, SQLA_String):
                    is_string_time = True
            except:
                pass

            is_string_time = True # 对于 SQLite 统一使用字符串对比更可靠
            query_cutoff = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
            logger.debug(f"[UniversalArchiver] 使用时间截止点 (String): {query_cutoff}")

            # 1. 查找待归档记录数量
            # 1. 查找待归档记录数量（只读 session）
            async with container.db.get_session() as session:
                count_stmt = select(func.count(model_class.id)).where(time_attr < query_cutoff)
                count_res = await session.execute(count_stmt)
                total_to_archive = count_res.scalar()
                
            if total_to_archive == 0:
                logger.info(f"[UniversalArchiver] 表 {table_name} 没有需要归档的数据")
                result.success = True
                result.end_time = datetime.now()
                return result
            
            logger.info(f"[UniversalArchiver] 发现 {total_to_archive} 条记录待归档")
            
            if dry_run:
                logger.info(f"[UniversalArchiver] Dry-run 模式，跳过实际操作")
                result.archived_count = total_to_archive
                result.success = True
                result.end_time = datetime.now()
                return result

            # 2. 分批处理 —— 每批独立 session，避免 identity map 缓存问题
            processed_count = 0
            while True:
                # 每批次独立开启 session
                async with container.db.get_session() as session:
                    stmt = select(model_class).where(
                        time_attr < query_cutoff
                    ).order_by(model_class.id).limit(self.batch_size)
                    
                    db_res = await session.execute(stmt)
                    rows = db_res.scalars().all()
                    
                    if not rows:
                        break
                        
                    # 转换为字典列表
                    dict_rows = [model_to_dict(r) for r in rows]
                    
                    # 确定分区日期
                    first_row_time = getattr(rows[0], time_column)
                    if isinstance(first_row_time, str):
                        try:
                            partition_dt = datetime.fromisoformat(first_row_time)
                        except:
                            partition_dt = datetime.now()
                    else:
                        partition_dt = first_row_time or datetime.now()

                    write_parquet(table_name, dict_rows, partition_dt)
                    
                    # 删除 SQLite 中的记录（分批删除，避免 SQLite 变量数限制 999）
                    ids_to_delete = [r.id for r in rows]
                    chunk_size = 500
                    for i in range(0, len(ids_to_delete), chunk_size):
                        chunk = ids_to_delete[i:i + chunk_size]
                        del_stmt = delete(model_class).where(model_class.id.in_(chunk))
                        await session.execute(del_stmt)
                    await session.commit()
                    
                    processed_count += len(rows)
                    result.archived_count = processed_count
                    logger.info(f"[UniversalArchiver] 已处理 {processed_count}/{total_to_archive} 条记录")

            result.success = True
            logger.info(f"[UniversalArchiver] 表 {table_name} 归档完成")
            
        except Exception as e:
            logger.error(f"[UniversalArchiver] 归档表 {table_name} 出错: {e}", exc_info=True)
            result.error = e
            result.success = False
            
        result.end_time = datetime.now()
        return result
