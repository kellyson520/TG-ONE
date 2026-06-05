from typing import Optional
from models.models import RuleLog, ChatStatistics, ErrorLog, RuleStatistics, ForwardRule, Chat
from sqlalchemy import select, update, insert, func
from sqlalchemy.orm import joinedload
from datetime import date, datetime
import asyncio
from core.helpers.db_utils import async_db_retry
import logging
from services.network.aimd import AIMDScheduler
from core.config import settings

logger = logging.getLogger(__name__)



def _evict_by_level(buffer: list, keep_ratio: float) -> list:
    """
    按日志等级智能驱逐。
    保留所有 ERROR/CRITICAL，从低优先级开始删除直到达到目标容量。
    驱逐顺序：DEBUG → INFO → WARNING → ERROR/CRITICAL（永不丢弃）
    """
    target_size = int(settings.STATS_LOG_BUFFER_HARD_CAP * keep_ratio)
    if len(buffer) <= target_size:
        return buffer

    HIGH   = [e for e in buffer if e.get("level") in ("ERROR", "CRITICAL")]
    MEDIUM = [e for e in buffer if e.get("level") == "WARNING"]
    LOW    = [e for e in buffer if e.get("level") in ("INFO", "DEBUG", None)]

    result = HIGH[:]  # ERROR/CRITICAL 全部保留
    remaining = target_size - len(result)
    if remaining > 0:
        result += MEDIUM[-remaining:]  # WARNING 取最新的
    remaining = target_size - len(result)
    if remaining > 0:
        result += LOW[-remaining:]     # INFO/DEBUG 取最新的

    evicted = len(buffer) - len(result)
    if evicted > 0:
        logger.warning(f"[LogBuffer] 驱逐完成：丢弃 {evicted} 条低优日志，保留 {len(result)} 条")
    return result


class StatsRepository:
    def __init__(self, db):
        self.db = db

        # ── 日志 Buffer（原有）───────────────────────────────
        self._log_buffer = []
        self._buffer_lock = asyncio.Lock()

        # ── Stats 内存累加器（CQRS，新增）────────────────────
        # key: (chat_id, date_str), val: {"forward_count": N, "saved_traffic_bytes": M}
        self._chat_stats_buffer: dict[tuple, dict] = {}
        # key: (rule_id, date_str), val: {"success_count": N, "error_count": M, ...}
        self._rule_stats_buffer: dict[tuple, dict] = {}
        self._stats_lock = asyncio.Lock()

        # ── AIMD 自适应调度器（新增）──────────────────────────
        self._flush_event = asyncio.Event()   # 大小触发唤醒信号
        self._flush_scheduler = AIMDScheduler(
            min_interval=settings.STATS_FLUSH_MIN_INTERVAL,
            max_interval=settings.STATS_FLUSH_MAX_INTERVAL,
            increment=settings.STATS_FLUSH_AIMD_INCREMENT,
            multiplier=settings.STATS_FLUSH_AIMD_MULTIPLIER
        )

        self._flush_task = None
        self._shutdown_event = asyncio.Event()

    async def archive_old_logs(self, hot_days_log: int = 30, hot_days_stats: int = 180) -> dict:
        """归档旧日志和统计数据。"""
        from core.archive.engine import UniversalArchiver
        from models.models import RuleLog, RuleStatistics, ChatStatistics

        archiver = UniversalArchiver()
        results = {}

        results["rule_logs"] = (await archiver.archive_table(
            model_class=RuleLog,
            hot_days=hot_days_log,
            time_column="created_at"
        )).to_dict()

        results["rule_statistics"] = (await archiver.archive_table(
            model_class=RuleStatistics,
            hot_days=hot_days_stats,
            time_column="created_at"
        )).to_dict()

        results["chat_statistics"] = (await archiver.archive_table(
            model_class=ChatStatistics,
            hot_days=hot_days_stats,
            time_column="created_at"
        )).to_dict()

        return results

    async def start(self):
        """启动后台双触发 AIMD flush 循环"""
        if self._flush_task is None:
            self._shutdown_event.clear()
            self._flush_task = asyncio.create_task(self._cron_flush())
            logger.info(f"统计缓冲刷新任务已启动 (AIMD 自适应调度 {settings.STATS_FLUSH_MIN_INTERVAL}s~{settings.STATS_FLUSH_MAX_INTERVAL}s, 双触发模式)")

    async def stop(self):
        """停止 flush 循环并排水所有剩余数据"""
        if self._flush_task:
            self._shutdown_event.set()
            self._flush_event.set()  # 唤醒循环使其能感知 shutdown
            try:
                await self._flush_task
            except asyncio.CancelledError as e:
                logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            self._flush_task = None
            # 优雅排水
            await asyncio.gather(self.flush_logs(), self.flush_stats(), return_exceptions=True)
            logger.info("统计缓冲刷新任务已停止，所有缓冲区已排水完毕")

    async def _cron_flush(self):
        """AIMD 自适应双触发刷新循环"""
        while not self._shutdown_event.is_set():
            interval = self._flush_scheduler.current_interval
            try:
                # 等待计时器超时，或被水位触发器提前唤醒
                await asyncio.wait_for(self._flush_event.wait(), timeout=interval)
                self._flush_event.clear()
            except asyncio.TimeoutError:
                pass  # 正常超时，执行定时 flush

            if self._shutdown_event.is_set():
                break

            # 执行 flush，根据实际积压量反馈 AIMD
            keys_before = len(self._chat_stats_buffer) + len(self._rule_stats_buffer)
            try:
                await asyncio.gather(
                    self.flush_logs(),
                    self.flush_stats(),
                    return_exceptions=True
                )
            except Exception as e:
                logger.error(f"Stats flush loop error: {e}")

            # AIMD 反馈：积压越多 → 间隔越短，越空闲 → 间隔越长
            had_pressure = keys_before > 10
            self._flush_scheduler.update(found_new_content=had_pressure)

    @async_db_retry(max_retries=5)
    async def flush_logs(self):
        """将缓冲的日志批量写入 DB"""
        logs_to_insert = []
        async with self._buffer_lock:
            if not self._log_buffer:
                return
            logs_to_insert = self._log_buffer[:]
            self._log_buffer.clear()

        if not logs_to_insert:
            return

        # 写入前移除 level 字段（DB 无此列，仅内存驱逐用）
        db_entries = [{k: v for k, v in e.items() if k != "level"} for e in logs_to_insert]

        try:
            async with self.db.get_session() as session:
                await session.execute(insert(RuleLog), db_entries)
                await session.commit()
                logger.debug(f"Flushed {len(db_entries)} logs to DB")
        except Exception as e:
            logger.error(f"Failed to flush logs to DB: {e}")

    @async_db_retry(max_retries=5)
    async def flush_stats(self):
        """批量将内存累加器 upsert 到 DB（一次事务，高效）"""
        async with self._stats_lock:
            if not self._chat_stats_buffer and not self._rule_stats_buffer:
                return
            chat_snap = dict(self._chat_stats_buffer)
            rule_snap = dict(self._rule_stats_buffer)
            self._chat_stats_buffer.clear()
            self._rule_stats_buffer.clear()

        try:
            async with self.db.get_session() as session:

                # 批量处理 ChatStatistics（upsert 累加）
                for (chat_id, dt), vals in chat_snap.items():
                    stmt = (
                        update(ChatStatistics)
                        .where(ChatStatistics.chat_id == chat_id, ChatStatistics.date == dt)
                        .values(
                            forward_count=ChatStatistics.forward_count + vals.get("forward_count", 0),
                            saved_traffic_bytes=ChatStatistics.saved_traffic_bytes + vals.get("saved_traffic_bytes", 0)
                        )
                    )
                    result = await session.execute(stmt)
                    if result.rowcount == 0:
                        try:
                            await session.execute(insert(ChatStatistics).values(
                                chat_id=chat_id, date=dt,
                                forward_count=vals.get("forward_count", 0),
                                saved_traffic_bytes=vals.get("saved_traffic_bytes", 0)
                            ))
                        except Exception:
                            # 并发竞争时可能已被插入，重试 UPDATE
                            await session.execute(stmt)

                # 批量处理 RuleStatistics（upsert 累加）
                for (rule_id, dt), vals in rule_snap.items():
                    stmt = (
                        update(RuleStatistics)
                        .where(RuleStatistics.rule_id == rule_id, RuleStatistics.date == dt)
                        .values(
                            total_triggered=RuleStatistics.total_triggered + vals.get("total_triggered", 0),
                            success_count=RuleStatistics.success_count + vals.get("success_count", 0),
                            error_count=RuleStatistics.error_count + vals.get("error_count", 0),
                            filtered_count=RuleStatistics.filtered_count + vals.get("filtered_count", 0),
                        )
                    )
                    result = await session.execute(stmt)
                    if result.rowcount == 0:
                        try:
                            await session.execute(insert(RuleStatistics).values(
                                rule_id=rule_id, date=dt,
                                total_triggered=vals.get("total_triggered", 0),
                                success_count=vals.get("success_count", 0),
                                error_count=vals.get("error_count", 0),
                                filtered_count=vals.get("filtered_count", 0),
                            ))
                        except Exception:
                            await session.execute(stmt)

                await session.commit()
                total_keys = len(chat_snap) + len(rule_snap)
                if total_keys > 0:
                    logger.debug(
                        f"[StatsFlush] 批量落库: chat={len(chat_snap)} entries, rule={len(rule_snap)} entries"
                    )
        except Exception as e:
            logger.error(f"[StatsFlush] 批量写入失败: {e}")

    async def log_action(self, rule_id, msg_id, status, result=None, msg_text=None, msg_type=None, processing_time=None):
        """记录详细日志 (Buffered, 三水位线 + 等级感知智能驱逐)"""
        # 根据 status 推断日志等级，供 _evict_by_level 分桶
        level = (
            "ERROR" if status in ("error", "failed") else
            "WARNING" if status == "filtered" else
            "INFO"
        )

        log_entry = {
            "rule_id": rule_id,
            "message_id": msg_id,
            "action": status,
            "message_text": msg_text[:500] if msg_text else None,
            "message_type": msg_type,
            "processing_time": int(processing_time) if processing_time is not None else None,
            "details": str(result) if result else "",
            "created_at": datetime.utcnow(),
            "level": level,  # ⬅ 仅内存驱逐用，flush 时会过滤掉
        }

        should_wake = False
        async with self._buffer_lock:
            size = len(self._log_buffer)

            if size >= settings.STATS_LOG_BUFFER_HARD_CAP:
                # 🔴 红色水位：强制驱逐，保留 ERROR/CRITICAL
                self._log_buffer = _evict_by_level(self._log_buffer, keep_ratio=0.6)
                logger.error(f"[LogBuffer] 触达红色水位({size})，已按等级强制驱逐")
                should_wake = True

            elif size >= settings.STATS_LOG_BUFFER_EVICT:
                # 🟠 橙色水位：驱逐低优日志 + 触发紧急 flush
                self._log_buffer = _evict_by_level(self._log_buffer, keep_ratio=0.8)
                logger.warning(f"[LogBuffer] 橙色水位({size})，驱逐低优日志")
                should_wake = True

            elif size >= settings.STATS_LOG_BUFFER_WARN:
                # 🟡 黄色水位：仅触发紧急 flush，不丢弃数据
                logger.warning(f"[LogBuffer] 黄色水位({size})，触发紧急 flush")
                should_wake = True

            self._log_buffer.append(log_entry)

            # 原有阈值触发（100 条）
            if len(self._log_buffer) >= 100:
                should_wake = True

        if should_wake:
            self._flush_event.set()  # 唤醒 AIMD 调度器立即执行 flush

    async def increment_stats(self, chat_id: int, saved_bytes: int = 0):
        """[CQRS] 纯内存累加，不触发任何 DB 操作"""
        today = date.today().isoformat()
        key = (chat_id, today)

        async with self._stats_lock:
            if key not in self._chat_stats_buffer:
                self._chat_stats_buffer[key] = {"forward_count": 0, "saved_traffic_bytes": 0}
            if saved_bytes == 0:
                self._chat_stats_buffer[key]["forward_count"] += 1
            else:
                self._chat_stats_buffer[key]["saved_traffic_bytes"] += saved_bytes
            key_count = len(self._chat_stats_buffer)

        # 水位检测（锁外执行，避免死锁）
        if key_count > settings.STATS_BUFFER_CAP:
            # 🔴 红色：同步阻塞 flush，stats 累加值不允许丢弃
            await self.flush_stats()
        elif key_count > settings.STATS_BUFFER_WARN:
            # 🟡 黄色：异步唤醒
            self._flush_event.set()

    async def increment_rule_stats(self, rule_id: int, status: str = "success"):
        """[CQRS] 纯内存累加，不触发任何 DB 操作"""
        today = date.today().isoformat()
        key = (rule_id, today)

        async with self._stats_lock:
            if key not in self._rule_stats_buffer:
                self._rule_stats_buffer[key] = {
                    "success_count": 0, "error_count": 0,
                    "filtered_count": 0, "total_triggered": 0
                }
            buf = self._rule_stats_buffer[key]
            buf["total_triggered"] += 1
            count_key = f"{status}_count"
            if count_key in buf:
                buf[count_key] += 1
            key_count = len(self._rule_stats_buffer)

        # 水位检测（锁外执行）
        if key_count > settings.STATS_BUFFER_CAP:
            await self.flush_stats()
        elif key_count > settings.STATS_BUFFER_WARN:
            self._flush_event.set()

    async def get_error_logs(self, page: int = 1, size: int = 20, level: str = None):
        """获取系统错误日志 (只读环境)"""
        async with self.db.get_session(readonly=True) as session:
            query = select(ErrorLog)
            if level:
                query = query.filter(ErrorLog.level == level.upper())
            count_result = await session.execute(select(func.count()).select_from(query.subquery()))
            total = count_result.scalar() or 0
            result = await session.execute(
                query
                .order_by(ErrorLog.id.desc())
                .offset((page-1)*size)
                .limit(size)
            )
            items = result.scalars().all()
            return {'items': items, 'total': total, 'total_pages': (total + size - 1) // size}

    async def get_rule_logs(self, rule_id: Optional[int] = None, page: int = 1, size: int = 50, query_str: str = None):
        """获取规则转发日志 (只读环境)"""
        async with self.db.get_session(readonly=True) as session:
            stmt_base = select(RuleLog)
            if query_str:
                from sqlalchemy import or_
                from sqlalchemy.orm import aliased
                search = f"%{query_str}%"
                source_chat = aliased(Chat)
                target_chat = aliased(Chat)
                stmt_base = (
                    stmt_base
                    .join(RuleLog.rule)
                    .join(source_chat, ForwardRule.source_chat_id == source_chat.id, isouter=True)
                    .join(target_chat, ForwardRule.target_chat_id == target_chat.id, isouter=True)
                    .filter(or_(
                        RuleLog.message_text.like(search),
                        RuleLog.details.like(search),
                        source_chat.title.like(search),
                        target_chat.title.like(search),
                        RuleLog.action.like(search)
                    ))
                )
            elif rule_id:
                stmt_base = stmt_base.filter(RuleLog.rule_id == rule_id)

            count_stmt = select(func.count()).select_from(stmt_base.subquery())
            total_res = await session.execute(count_stmt)
            total = total_res.scalar() or 0

            stmt = (
                stmt_base
                .options(
                    joinedload(RuleLog.rule).joinedload(ForwardRule.source_chat),
                    joinedload(RuleLog.rule).joinedload(ForwardRule.target_chat)
                )
                .order_by(RuleLog.id.desc())
                .offset((page-1)*size)
                .limit(size)
            )
            result = await session.execute(stmt)
            items = result.scalars().all()
            return items, total

    async def get_message_type_distribution(self):
        """获取消息类型分布统计 (只读)"""
        async with self.db.get_session(readonly=True) as session:
            stmt = (
                select(
                    RuleLog.message_type,
                    func.count(RuleLog.id).label('count')
                )
                .group_by(RuleLog.message_type)
                .order_by(func.count(RuleLog.id).desc())
            )
            result = await session.execute(stmt)
            return [{'name': row.message_type or 'Unknown', 'value': row.count} for row in result]

    async def get_recent_activity(self, limit: int = 10):
        """获取最近的系统 activity 日志 (只读)"""
        async with self.db.get_session(readonly=True) as session:
            stmt = (
                select(RuleLog)
                .options(
                    joinedload(RuleLog.rule).joinedload(ForwardRule.source_chat),
                    joinedload(RuleLog.rule).joinedload(ForwardRule.target_chat)
                )
                .order_by(RuleLog.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_hourly_trend(self, hours: int = 24):
        """获取最近 N 小时的转发趋势 (只读)"""
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

        async with self.db.get_session(readonly=True) as session:
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
        """批量获取规则的累计统计数据 (只读)"""
        if not rule_ids:
            return {}

        async with self.db.get_session(readonly=True) as session:
            stmt = (
                select(
                    RuleStatistics.rule_id,
                    func.sum(RuleStatistics.total_triggered).label('processed'),
                    func.sum(RuleStatistics.success_count).label('forwarded'),
                    func.sum(RuleStatistics.error_count).label('error'),
                    func.sum(RuleStatistics.filtered_count).label('filtered')
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
                    'error': int(row.error or 0),
                    'filtered': int(row.filtered or 0)
                }

            for rid in rule_ids:
                if rid not in stats_map:
                    stats_map[rid] = {'processed': 0, 'forwarded': 0, 'error': 0, 'filtered': 0}

            return stats_map