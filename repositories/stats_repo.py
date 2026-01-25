from typing import Optional
from models.models import RuleLog, ChatStatistics, ErrorLog, RuleStatistics
from sqlalchemy import select, update, insert, func
from datetime import date, datetime
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class StatsRepository:
    def __init__(self, db):
        self.db = db
        self._log_buffer = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task = None
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start background flushing task"""
        if self._flush_task is None:
            self._shutdown_event.clear()
            self._flush_task = asyncio.create_task(self._cron_flush())
            logger.info("Stats buffer flush task started")

    async def stop(self):
        """Stop background flushing task and flush remaining"""
        if self._flush_task:
            self._shutdown_event.set()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
            # Final flush
            await self.flush_logs()
            logger.info("Stats buffer flush task stopped")

    async def _cron_flush(self):
        """Periodic flush loop"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(5)  # Flash every 5 seconds
                await self.flush_logs()
            except Exception as e:
                logger.error(f"Stats flush loop error: {e}")

    async def flush_logs(self):
        """Flush buffered logs to database"""
        logs_to_insert = []
        async with self._buffer_lock:
            if not self._log_buffer:
                return
            logs_to_insert = self._log_buffer[:]
            self._log_buffer.clear()
        
        if not logs_to_insert:
            return

        try:
            async with self.db.session() as session:
                await session.execute(insert(RuleLog), logs_to_insert)
                await session.commit()
                logger.debug(f"Flushed {len(logs_to_insert)} logs to DB")
        except Exception as e:
            logger.error(f"Failed to flush logs to DB: {e}")
            # Optional: Retry logic or drop? For logs, dropping is acceptable to avoid deadlock.
            # But let's log error.

    async def log_action(self, rule_id, msg_id, status, result=None):
        """记录详细日志 (Buffered)"""
        # Create log entry dictionary
        # RuleLog expects: rule_id, action, source_message_id, result
        log_entry = {
            "rule_id": rule_id,
            "source_message_id": msg_id,
            "action": status,
            "result": str(result) if result else "",
            # created_at handled by DB default or we should set it if using insert()
            # Since we use bulk insert, we MUST provide all fields usually if we skip ORM
            # But insert(RuleLog) works with default values if schema defines them?
            # models.py says default=lambda... which is Python Side.
            # So we MUST generate it here.
            "created_at": datetime.utcnow().isoformat()
        }
        
        async with self._buffer_lock:
            self._log_buffer.append(log_entry)
            should_flush = len(self._log_buffer) >= 100
        
        if should_flush:
            asyncio.create_task(self.flush_logs())

    async def increment_stats(self, chat_id: int):
        """[Scheme 7 Standard] 原子级聊天统计更新"""
        today = date.today().isoformat()
        async with self.db.session() as session:
            # 尝试直接原子递增
            stmt = (
                update(ChatStatistics)
                .where(
                    ChatStatistics.chat_id == chat_id,
                    ChatStatistics.date == today
                )
                .values(forward_count=ChatStatistics.forward_count + 1)
            )
            result = await session.execute(stmt)
            
            if result.rowcount == 0:
                try:
                    stmt_insert = insert(ChatStatistics).values(
                        chat_id=chat_id, 
                        date=today, 
                        forward_count=1
                    )
                    await session.execute(stmt_insert)
                except Exception:
                    await session.execute(stmt)
            
        await session.commit()

    async def increment_rule_stats(self, rule_id: int, status: str = "success"):
        """原子级规则统计更新 (success, error, filtered)"""
        today = date.today().isoformat()
        
        # 确定要更新的字段
        if status == "success":
            update_values = {RuleStatistics.forwarded_count: RuleStatistics.forwarded_count + 1}
            insert_values = {"forwarded_count": 1}
        elif status == "error":
            update_values = {RuleStatistics.error_count: RuleStatistics.error_count + 1}
            insert_values = {"error_count": 1}
        elif status == "filtered":
            update_values = {RuleStatistics.filtered_count: RuleStatistics.filtered_count + 1}
            insert_values = {"filtered_count": 1}
        else:
            update_values = {RuleStatistics.processed_count: RuleStatistics.processed_count + 1}
            insert_values = {"processed_count": 1}

        # 始终递增处理总数
        update_values[RuleStatistics.processed_count] = RuleStatistics.processed_count + 1
        if "processed_count" not in insert_values:
            insert_values["processed_count"] = 1

        async with self.db.session() as session:
            stmt = (
                update(RuleStatistics)
                .where(
                    RuleStatistics.rule_id == rule_id,
                    RuleStatistics.date == today
                )
                .values(update_values)
            )
            result = await session.execute(stmt)
            
            if result.rowcount == 0:
                try:
                    stmt_insert = insert(RuleStatistics).values(
                        rule_id=rule_id, 
                        date=today, 
                        **insert_values
                    )
                    await session.execute(stmt_insert)
                except Exception:
                    await session.execute(stmt)
            
        await session.commit()


    async def get_error_logs(self, page: int = 1, size: int = 20, level: str = None):
        """获取系统错误日志，支持分页和级别筛选"""
        async with self.db.session() as session:
            # 构建查询
            query = select(ErrorLog)
            
            # 添加级别筛选
            if level:
                query = query.filter(ErrorLog.level == level.upper())
            
            # 获取总数
            count_result = await session.execute(select(func.count()).select_from(query.subquery()))
            total = count_result.scalar() or 0
            
            # 获取分页数据
            result = await session.execute(
                query
                .order_by(ErrorLog.id.desc())
                .offset((page-1)*size)
                .limit(size)
            )
            items = result.scalars().all()
            
    async def get_rule_logs(self, rule_id: Optional[int] = None, page: int = 1, size: int = 50):
        """获取规则转发日志"""
        async with self.db.session() as session:
            query = select(RuleLog)
            if rule_id:
                query = query.filter(RuleLog.rule_id == rule_id)
            
            # Count total
            count_result = await session.execute(select(func.count()).select_from(query.subquery()))
            total = count_result.scalar() or 0
            
            # Get items
            result = await session.execute(
                query
                .order_by(RuleLog.id.desc())
                .offset((page-1)*size)
                .limit(size)
            )
            items = result.scalars().all()
            return items, total

    async def get_hourly_trend(self, hours: int = 24):
        """获取最近 N 小时的转发趋势"""
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        async with self.db.session() as session:
            # 使用 SQLite 的 strftime 来按小时分组 (YYYY-MM-DDTHH)
            # 兼容 ISO 格式: 2026-01-11T12:34:56.789
            stmt = (
                select(
                    func.strftime('%Y-%m-%dT%H', RuleLog.created_at).label('hour'),
                    func.count(RuleLog.id).label('count')
                )
                .where(RuleLog.created_at >= cutoff)
                .group_by('hour')
                .order_by('hour')
            )
            result = await session.execute(stmt)
            return [{'hour': row.hour, 'count': row.count} for row in result]

    async def get_rules_stats_batch(self, rule_ids: list[int]):
        """批量获取规则的累计统计数据"""
        from models.models import RuleStatistics
        
        if not rule_ids:
            return {}
            
        async with self.db.session() as session:
            # 聚合查询: sum(processed), sum(forwarded), sum(error) group by rule_id
            stmt = (
                select(
                    RuleStatistics.rule_id,
                    func.sum(RuleStatistics.processed_count).label('processed'),
                    func.sum(RuleStatistics.forwarded_count).label('forwarded'),
                    func.sum(RuleStatistics.error_count).label('error')
                )
                .where(RuleStatistics.rule_id.in_(rule_ids))
                .group_by(RuleStatistics.rule_id)
            )
            
            result = await session.execute(stmt)
            stats_map = {}
            for row in result:
                stats_map[row.rule_id] = {
                    'processed': int(row.processed or 0),
                    'forwarded': int(row.forwarded or 0),
                    'error': int(row.error or 0)
                }
                
            # Fill missing with zeros
            for rid in rule_ids:
                if rid not in stats_map:
                    stats_map[rid] = {'processed': 0, 'forwarded': 0, 'error': 0}
                    
            return stats_map