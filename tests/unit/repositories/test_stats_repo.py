"""
tests/unit/repositories/test_stats_repo.py

覆盖 StatsRepository 改造后的所有新行为：
  - CQRS 纯内存累加（不触发 DB）
  - flush_stats() 批量 upsert
  - 三水位线 + 等级感知驱逐 (_evict_by_level)
  - AIMD 双触发 _cron_flush
  - stop() 优雅排水
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, func

from repositories.stats_repo import StatsRepository, _evict_by_level
from models.models import RuleLog, RuleStatistics, ChatStatistics
from core.container import container
from core.config import settings
from datetime import date


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def repo():
    """工厂：返回一个挂载到内存数据库的 StatsRepository"""
    return StatsRepository(container.db)


# ─────────────────────────────────────────────────────────────
# 辅助函数测试
# ─────────────────────────────────────────────────────────────
class TestEvictByLevel:
    """_evict_by_level 等级感知驱逐策略"""

    def _make_buf(self, levels: list[str]) -> list[dict]:
        return [{"level": lvl, "id": i} for i, lvl in enumerate(levels)]

    def test_no_eviction_when_below_target(self):
        buf = self._make_buf(["INFO"] * 10)
        # keep_ratio=1.0 → target = HARD_CAP，10 < HARD_CAP，不驱逐
        result = _evict_by_level(buf, keep_ratio=1.0)
        assert result == buf

    def test_error_critical_always_kept(self):
        """ERROR/CRITICAL 无论如何都不应被丢弃"""
        levels = ["INFO"] * 5000 + ["ERROR"] * 3 + ["CRITICAL"] * 2
        buf = self._make_buf(levels)
        result = _evict_by_level(buf, keep_ratio=0.1)
        result_levels = {e["level"] for e in result}
        assert "ERROR" in result_levels
        assert "CRITICAL" in result_levels

    def test_low_priority_evicted_first(self):
        """DEBUG/INFO 先被驱逐，WARNING 其次"""
        # 构造刚好超出目标的 buffer
        buf = (
            self._make_buf(["DEBUG"] * 2000)
            + self._make_buf(["INFO"] * 2000)
            + self._make_buf(["WARNING"] * 500)
            + self._make_buf(["ERROR"] * 100)
        )
        # keep 80% of HARD_CAP
        target = int(settings.STATS_LOG_BUFFER_HARD_CAP * 0.8)
        result = _evict_by_level(buf, keep_ratio=0.8)
        assert len(result) <= target
        # ERROR 全部保留
        error_count = sum(1 for e in result if e["level"] == "ERROR")
        assert error_count == 100

    def test_result_size_within_target(self):
        """驱逐后长度不超过 target_size"""
        buf = self._make_buf(["INFO"] * settings.STATS_LOG_BUFFER_HARD_CAP)
        result = _evict_by_level(buf, keep_ratio=0.6)
        assert len(result) <= int(settings.STATS_LOG_BUFFER_HARD_CAP * 0.6)


# ─────────────────────────────────────────────────────────────
# CQRS 纯内存累加测试
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestIncrementStats:

    async def test_no_db_write_on_increment(self, repo, db):
        """increment_stats 调用后 DB 中不应有任何新数据"""
        await repo.increment_stats(chat_id=999)
        stmt = select(func.count(ChatStatistics.id))
        count = (await db.execute(stmt)).scalar()
        assert count == 0, "increment_stats 不该直接写 DB"

    async def test_in_memory_accumulation(self, repo):
        """连续 3 次 increment 应在内存中累加"""
        for _ in range(3):
            await repo.increment_stats(chat_id=11)
        today = date.today().isoformat()
        assert repo._chat_stats_buffer[(11, today)]["forward_count"] == 3

    async def test_bytes_accumulation(self, repo):
        """saved_bytes 参数应累加到 saved_traffic_bytes"""
        await repo.increment_stats(chat_id=22, saved_bytes=1024)
        await repo.increment_stats(chat_id=22, saved_bytes=2048)
        today = date.today().isoformat()
        val = repo._chat_stats_buffer[(22, today)]["saved_traffic_bytes"]
        assert val == 3072


@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestIncrementRuleStats:

    async def test_no_db_write_on_increment(self, repo, db):
        """increment_rule_stats 不触发 DB"""
        await repo.increment_rule_stats(rule_id=55, status="success")
        stmt = select(func.count(RuleStatistics.id))
        count = (await db.execute(stmt)).scalar()
        assert count == 0

    async def test_total_triggered_accumulated(self, repo):
        """total_triggered 每次调用都 +1"""
        for _ in range(5):
            await repo.increment_rule_stats(rule_id=77, status="success")
        today = date.today().isoformat()
        assert repo._rule_stats_buffer[(77, today)]["total_triggered"] == 5

    async def test_status_counters(self, repo):
        """success / error / filtered 分别累加"""
        await repo.increment_rule_stats(rule_id=88, status="success")
        await repo.increment_rule_stats(rule_id=88, status="error")
        await repo.increment_rule_stats(rule_id=88, status="filtered")
        today = date.today().isoformat()
        buf = repo._rule_stats_buffer[(88, today)]
        assert buf["success_count"] == 1
        assert buf["error_count"] == 1
        assert buf["filtered_count"] == 1
        assert buf["total_triggered"] == 3


# ─────────────────────────────────────────────────────────────
# flush_stats 批量落库测试
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestFlushStats:

    async def test_flush_writes_chat_stats(self, repo, db):
        """flush_stats 应将内存数据批量写入 ChatStatistics"""
        await repo.increment_stats(chat_id=101)
        await repo.increment_stats(chat_id=101)
        await repo.flush_stats()

        stmt = select(ChatStatistics).where(ChatStatistics.chat_id == 101)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.forward_count == 2

    async def test_flush_writes_rule_stats(self, repo, db):
        """flush_stats 应将内存数据批量写入 RuleStatistics"""
        await repo.increment_rule_stats(rule_id=202, status="success")
        await repo.increment_rule_stats(rule_id=202, status="success")
        await repo.flush_stats()

        today = date.today().isoformat()
        stmt = select(RuleStatistics).where(
            RuleStatistics.rule_id == 202,
            RuleStatistics.date == today
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.success_count == 2
        assert row.total_triggered == 2

    async def test_flush_clears_buffer(self, repo):
        """flush 后 buffer 应清空"""
        await repo.increment_stats(chat_id=303)
        await repo.flush_stats()
        assert len(repo._chat_stats_buffer) == 0
        assert len(repo._rule_stats_buffer) == 0

    async def test_double_flush_accumulates(self, repo, db):
        """两批 flush 的累加值应合并（upsert 累加而非覆盖）"""
        await repo.increment_stats(chat_id=404)
        await repo.flush_stats()
        await repo.increment_stats(chat_id=404)
        await repo.increment_stats(chat_id=404)
        await repo.flush_stats()

        stmt = select(ChatStatistics).where(ChatStatistics.chat_id == 404)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.forward_count == 3  # 1 + 2

    async def test_flush_noop_when_empty(self, repo, db):
        """空 buffer 时 flush 不应写入任何行"""
        assert len(repo._chat_stats_buffer) == 0
        await repo.flush_stats()  # 不应抛错
        stmt = select(func.count(ChatStatistics.id))
        count = (await db.execute(stmt)).scalar()
        assert count == 0


# ─────────────────────────────────────────────────────────────
# log_action 三水位线测试
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
class TestLogActionWatermarks:

    async def test_log_buffered_no_db_write(self, repo, db):
        """写入 5 条日志后 DB 仍为空"""
        for i in range(5):
            await repo.log_action(rule_id=1, msg_id=i, status="success")
        stmt = select(func.count(RuleLog.id))
        count = (await db.execute(stmt)).scalar()
        assert count == 0

    async def test_flush_event_set_at_warn_watermark(self, repo):
        """黄色水位时应唤醒 _flush_event"""
        repo._flush_event.clear()
        # 预填至黄色水位 - 1
        async with repo._buffer_lock:
            repo._log_buffer = [{"level": "INFO"}] * (settings.STATS_LOG_BUFFER_WARN - 1)
        # 触发第 WARN 条
        await repo.log_action(rule_id=1, msg_id=9999, status="success")
        assert repo._flush_event.is_set(), "黄色水位应 set _flush_event"

    async def test_eviction_at_evict_watermark(self, repo):
        """橙色水位：驱逐后 buffer 总长度应小于 HARD_CAP（而非 EVICT 本身）"""
        async with repo._buffer_lock:
            repo._log_buffer = [{"level": "INFO"}] * settings.STATS_LOG_BUFFER_EVICT
        await repo.log_action(rule_id=1, msg_id=8888, status="success")
        # 驱逐按 keep_ratio=0.8 执行，结果 + 新 append 的 1 条
        expected_max = int(settings.STATS_LOG_BUFFER_HARD_CAP * 0.8) + 1
        assert len(repo._log_buffer) <= expected_max

    async def test_error_logs_survive_eviction(self, repo):
        """ERROR 级日志在橙色水位驱逐中必须保留"""
        error_entries = [{"level": "ERROR"} for _ in range(10)]
        info_entries = [{"level": "INFO"}] * (settings.STATS_LOG_BUFFER_EVICT - 10)
        async with repo._buffer_lock:
            repo._log_buffer = info_entries + error_entries
        await repo.log_action(rule_id=1, msg_id=7777, status="success")
        error_count = sum(1 for e in repo._log_buffer if e.get("level") == "ERROR")
        assert error_count == 10

    async def test_level_field_stripped_on_flush(self, repo, db):
        """flush 时 level 字段应从入库数据中过滤掉"""
        await repo.log_action(rule_id=1, msg_id=1, status="error")
        await repo.flush_logs()
        stmt = select(RuleLog).limit(1)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        # RuleLog 中没有 level 列，正常入库即表示过滤成功
        assert row is not None


# ─────────────────────────────────────────────────────────────
# AIMD 调度 / stop 优雅排水测试
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
class TestLifecycle:

    async def test_start_creates_task(self, repo):
        """start() 应创建后台任务"""
        await repo.start()
        assert repo._flush_task is not None
        assert not repo._flush_task.done()
        await repo.stop()

    async def test_stop_drains_buffers(self, repo, db):
        """stop() 应排水所有剩余 stats 数据"""
        await repo.start()
        await repo.increment_stats(chat_id=555)
        await repo.increment_stats(chat_id=555)
        await repo.stop()

        stmt = select(ChatStatistics).where(ChatStatistics.chat_id == 555)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.forward_count == 2

    async def test_stop_clears_task_reference(self, repo):
        """stop() 后 _flush_task 应置 None"""
        await repo.start()
        await repo.stop()
        assert repo._flush_task is None

    async def test_aimd_pressure_shortens_interval(self, repo):
        """高积压时 AIMD 应缩短 current_interval"""
        await repo.start()
        initial_interval = repo._flush_scheduler.current_interval
        # 模拟大量积压 (> 10 keys)
        today = date.today().isoformat()
        for i in range(20):
            repo._chat_stats_buffer[(i, today)] = {"forward_count": 1, "saved_traffic_bytes": 0}
        # 让 AIMD 跑一轮
        repo._flush_event.set()
        await asyncio.sleep(0.05)
        new_interval = repo._flush_scheduler.current_interval
        assert new_interval <= initial_interval
        await repo.stop()

    async def test_aimd_idle_extends_interval(self, repo):
        """空闲时（buffer 为空）AIMD 应延长 current_interval"""
        await repo.start()
        # 确保 buffer 为空 → 模拟空闲
        repo._chat_stats_buffer.clear()
        repo._rule_stats_buffer.clear()
        before = repo._flush_scheduler.current_interval
        # 唤醒执行一轮 flush
        repo._flush_event.set()
        await asyncio.sleep(0.05)
        after = repo._flush_scheduler.current_interval
        assert after >= before
        await repo.stop()

    async def test_stats_buffer_cap_triggers_sync_flush(self, repo, db):
        """红色水位：increment_stats 应同步 await flush_stats（buffer 清空）"""
        today = date.today().isoformat()
        # 填满至 CAP
        async with repo._stats_lock:
            for i in range(settings.STATS_BUFFER_CAP + 1):
                repo._chat_stats_buffer[(i, today)] = {
                    "forward_count": 1,
                    "saved_traffic_bytes": 0
                }
        # 再 increment 一次，应触发同步 flush
        await repo.increment_stats(chat_id=9999)
        # flush 后内存应被清空
        assert len(repo._chat_stats_buffer) < settings.STATS_BUFFER_CAP


# ─────────────────────────────────────────────────────────────
# 原有读取接口（回归测试）
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestReadInterface:

    async def test_get_rules_stats_batch_missing_filled(self, repo):
        """缺失规则 ID 应用 0 填充"""
        stats = await repo.get_rules_stats_batch([9001, 9002])
        assert stats[9001]["forwarded"] == 0
        assert stats[9002]["error"] == 0

    async def test_get_rules_stats_batch_correct_sum(self, repo, db):
        """累加两天的数据后 batch 应正确求和"""
        rows = [
            RuleStatistics(rule_id=1, date="2025-01-01", success_count=10, total_triggered=10),
            RuleStatistics(rule_id=1, date="2025-01-02", success_count=5, total_triggered=6),
        ]
        db.add_all(rows)
        await db.commit()

        stats = await repo.get_rules_stats_batch([1])
        assert stats[1]["forwarded"] == 15
        assert stats[1]["processed"] == 16
