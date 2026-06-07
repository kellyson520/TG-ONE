import pytest
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

# 设置测试环境路径
TEST_HOT_DIR = Path("tests/temp/hot_test_data")

@pytest.fixture(autouse=True)
def mock_settings_hot_dir(monkeypatch):
    """强制在测试中使用临时的 HOT_DIR"""
    monkeypatch.setattr("core.config.settings.HOT_DIR", TEST_HOT_DIR)
    monkeypatch.setattr("core.config.settings.HOTWORD_SYNC_INTERVAL", 0.1)
    monkeypatch.setattr("core.config.settings.HOTWORD_BATCH_SIZE", 2)
    monkeypatch.setattr("core.config.settings.HOTWORD_IDLE_TIMEOUT", 1.0)
    
    if TEST_HOT_DIR.exists():
        shutil.rmtree(TEST_HOT_DIR)
    TEST_HOT_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if TEST_HOT_DIR.exists():
        shutil.rmtree(TEST_HOT_DIR)

@pytest.mark.asyncio
async def test_hotword_full_lifecycle():
    from services.hotword_service import HotwordService
    service = HotwordService()
    
    # 1. 测试批次处理与 L1 缓存
    channel = "test_chan"
    texts = ["今天天气不错", "上海的天气真的不错", "测试分词系统"]
    
    await service.process_batch(channel, texts)
    
    assert channel in service.l1_cache
    assert "global" in service.l1_cache
    # 检查是否有分词结果 (由于使用真实词库，检查 key 数量)
    assert len(service.l1_cache[channel]) > 0
    
    # 2. 测试刷写磁盘
    await service.flush_to_disk()
    assert len(service.l1_cache) == 0
    
    # 检查数据库持久化
    ranks_from_db = await service.repo.load_rankings(channel, "_temp")
    assert len(ranks_from_db) > 0
    
    # 3. 测试排行榜查询 (实时查询会回退到 temp)
    ranks = await service.get_rankings(channel, period="day")
    assert len(ranks) > 0
    # 验证排序：第一个权重应该最大
    assert ranks[0][1] >= ranks[-1][1]

    # 4. 测试模糊匹配
    matches = await service.fuzzy_match_channel("test")
    assert channel in matches

@pytest.mark.asyncio
async def test_hotword_aggregation():
    from services.hotword_service import HotwordService
    service = HotwordService()
    channel = "agg_chan"
    from sqlalchemy import text
    async with service.repo.session_factory() as session:
        await session.execute(text(f"DELETE FROM hot_period_stats WHERE channel='{channel}'"))
        await session.execute(text(f"DELETE FROM hot_raw_stats WHERE channel='{channel}'"))
        await session.commit()
    
    # 模拟昨天的日报数据
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    
    # 准备 temp 数据到数据库
    await service.repo.save_temp_counts(channel, {"测试": {"f": 10.0, "u": 1}, "聚合": {"f": 5.0, "u": 1}})
        
    # 执行每日聚合
    await service.aggregate_daily()
    
    # 检查 temp 是否消失，day 是否生成
    temp_data = await service.repo.load_rankings(channel, "_temp")
    assert len(temp_data) == 0
    
    day_data = await service.repo.load_rankings(channel, f"day_{yesterday}")
    assert "测试" in day_data
    assert day_data["测试"]["f"] == 10.0
    
    # 5. 测试月度聚合
    # 手动插入两个日数据
    curr_month = datetime.now().strftime("%Y%m")
    
    from models.hotword import HotPeriodStats
    
    async with service.repo.session_factory() as session:
        # 插入两条数据
        p1 = HotPeriodStats(channel=channel, word="月", period="day", date_key=f"{curr_month}01", score=1.0, user_count=1)
        p2 = HotPeriodStats(channel=channel, word="月", period="day", date_key=f"{curr_month}02", score=2.0, user_count=1)
        session.add_all([p1, p2])
        await session.commit()
    
    # 下个月初执行上月聚合测试
    with patch('services.hotword_service.datetime') as mock_date:
        mock_date.now.return_value = datetime.now() + timedelta(days=32)
        await service.aggregate_monthly()
    
    month_data = await service.repo.load_rankings(channel, f"month_{curr_month}")
    assert "月" in month_data
    assert month_data["月"]["f"] == 3.0

@pytest.mark.asyncio
async def test_hotword_rankings_read_archived_periods_when_raw_is_empty():
    from services.hotword_service import HotwordService
    from models.hotword import HotPeriodStats

    service = HotwordService()
    channel = "period_only_chan"
    year_channel = "period_only_year_chan"
    year_day_channel = "period_only_year_day_chan"
    curr_month = datetime.now().strftime("%Y%m")
    curr_year = datetime.now().strftime("%Y")

    from sqlalchemy import text
    async with service.repo.session_factory() as session:
        await session.execute(text(f"DELETE FROM hot_period_stats WHERE channel='{channel}'"))
        await session.execute(text(f"DELETE FROM hot_raw_stats WHERE channel='{channel}'"))
        await session.execute(text(f"DELETE FROM hot_period_stats WHERE channel='{year_channel}'"))
        await session.execute(text(f"DELETE FROM hot_raw_stats WHERE channel='{year_channel}'"))
        await session.execute(text(f"DELETE FROM hot_period_stats WHERE channel='{year_day_channel}'"))
        await session.execute(text(f"DELETE FROM hot_raw_stats WHERE channel='{year_day_channel}'"))
        session.add_all([
            HotPeriodStats(channel=channel, word="日榜", period="day", date_key=f"{curr_month}01", score=8.0, user_count=2),
            HotPeriodStats(channel=channel, word="月榜", period="day", date_key=f"{curr_month}02", score=5.0, user_count=1),
            HotPeriodStats(channel=year_channel, word="年榜", period="month", date_key=curr_month, score=13.0, user_count=3),
            HotPeriodStats(channel=year_day_channel, word="全年日榜", period="day", date_key=f"{curr_year}0102", score=21.0, user_count=4),
        ])
        await session.commit()

    channels = await service.repo.get_channel_dirs()
    assert channel in channels
    assert year_channel in channels
    assert year_day_channel in channels

    day_ranks = dict(await service.get_rankings(channel, period="day"))
    month_ranks = dict(await service.get_rankings(channel, period="month"))
    year_ranks = dict(await service.get_rankings(year_channel, period="year"))
    year_day_ranks = dict(await service.get_rankings(year_day_channel, period="year"))

    assert day_ranks["月榜"] == 5 or day_ranks["日榜"] == 8
    assert month_ranks["日榜"] == 8
    assert month_ranks["月榜"] == 5
    assert year_ranks["年榜"] == 13
    assert year_day_ranks["全年日榜"] == 21

@pytest.mark.asyncio
async def test_hotword_resolves_callback_token_from_archived_channels():
    from services.hotword_service import HotwordService
    from models.hotword import HotPeriodStats
    from sqlalchemy import text
    from ui.hotword_callback_codec import make_hotword_channel_token

    service = HotwordService()
    channel = "长期存在的频道:月榜"
    token = make_hotword_channel_token(channel)

    async with service.repo.session_factory() as session:
        await session.execute(
            text("DELETE FROM hot_period_stats WHERE channel = :channel"),
            {"channel": channel},
        )
        session.add(
            HotPeriodStats(
                channel=channel,
                word="稳定token",
                period="month",
                date_key=datetime.now().strftime("%Y%m"),
                score=3.0,
                user_count=1,
            )
        )
        await session.commit()

    assert await service.resolve_channel_token(token) == channel
    assert await service.resolve_channel_token("not-a-token") is None

@pytest.mark.asyncio
async def test_hotword_global_month_prefers_direct_global_archive():
    from services.hotword_service import HotwordService
    from models.hotword import HotPeriodStats
    from sqlalchemy import text

    service = HotwordService()
    month_key = datetime.now().strftime("%Y%m")
    channel = "global_month_fallback_probe"

    async with service.repo.session_factory() as session:
        await session.execute(
            text("DELETE FROM hot_period_stats WHERE channel IN ('global', :channel)"),
            {"channel": channel},
        )
        session.add_all([
            HotPeriodStats(
                channel="global",
                word="全局直读",
                period="month",
                date_key=month_key,
                score=99999.0,
                user_count=10,
            ),
            HotPeriodStats(
                channel=channel,
                word="频道回退",
                period="month",
                date_key=month_key,
                score=99999.0,
                user_count=10,
            ),
        ])
        await session.commit()

    ranks = dict(await service.get_rankings("global", period="month"))

    assert ranks["全局直读"] == 99999
    assert "频道回退" not in ranks


@pytest.mark.asyncio
async def test_hotword_load_rankings_parses_period_from_suffix_not_channel_name():
    from repositories.hotword_repo import HotwordRepository
    from models.hotword import HotPeriodStats
    from sqlalchemy import text

    repo = HotwordRepository()
    month_key = datetime.now().strftime("%Y%m")
    numeric_channel = "RED讨论组【2025复活版】"
    day_named_channel = "daydream频道"

    async with repo.session_factory() as session:
        await session.execute(
            text("DELETE FROM hot_period_stats WHERE channel IN (:numeric_channel, :day_named_channel)"),
            {
                "numeric_channel": numeric_channel,
                "day_named_channel": day_named_channel,
            },
        )
        session.add_all([
            HotPeriodStats(
                channel=numeric_channel,
                word="数字频道月榜",
                period="month",
                date_key=month_key,
                score=7.0,
                user_count=2,
            ),
            HotPeriodStats(
                channel=day_named_channel,
                word="day频道月榜",
                period="month",
                date_key=month_key,
                score=5.0,
                user_count=1,
            ),
        ])
        await session.commit()

    numeric_data = await repo.load_rankings(
        numeric_channel,
        f"{numeric_channel}_month_{month_key}.json",
    )
    day_named_data = await repo.load_rankings(
        day_named_channel,
        f"{day_named_channel}_month_{month_key}.json",
    )

    assert numeric_data["数字频道月榜"]["f"] == 7.0
    assert day_named_data["day频道月榜"]["f"] == 5.0


@pytest.mark.asyncio
async def test_hotword_global_day_uses_batched_channel_snapshot():
    from services.hotword_service import HotwordService
    from models.hotword import HotRawStats, HotPeriodStats
    from sqlalchemy import text

    service = HotwordService()
    today = datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    current_channel = "global_day_batch_current"
    raw_channel = "global_day_batch_raw"
    fallback_channel = "global_day_batch_fallback"

    async with service.repo.session_factory() as session:
        await session.execute(
            text(
                "DELETE FROM hot_period_stats "
                "WHERE channel IN (:current_channel, :raw_channel, :fallback_channel)"
            ),
            {
                "current_channel": current_channel,
                "raw_channel": raw_channel,
                "fallback_channel": fallback_channel,
            },
        )
        await session.execute(
            text(
                "DELETE FROM hot_raw_stats "
                "WHERE channel IN (:current_channel, :raw_channel, :fallback_channel)"
            ),
            {
                "current_channel": current_channel,
                "raw_channel": raw_channel,
                "fallback_channel": fallback_channel,
            },
        )
        session.add_all([
            HotPeriodStats(
                channel=current_channel,
                word="今日批量",
                period="day",
                date_key=today,
                score=50.0,
                user_count=5,
            ),
            HotPeriodStats(
                channel=current_channel,
                word="不该回退",
                period="day",
                date_key=yesterday,
                score=9999.0,
                user_count=5,
            ),
            HotPeriodStats(
                channel=fallback_channel,
                word="最近回退",
                period="day",
                date_key=yesterday,
                score=40.0,
                user_count=4,
            ),
            HotRawStats(
                channel=raw_channel,
                word="实时批量",
                score=45.0,
                unique_users=3,
            ),
        ])
        await session.commit()

    ranks = dict(await service.get_rankings("global", period="day"))

    assert ranks["今日批量"] == 50
    assert ranks["实时批量"] == 45
    assert ranks["最近回退"] == 40
    assert "不该回退" not in ranks


@pytest.mark.asyncio
async def test_hotword_temp_counts_batch_upsert_accumulates():
    from services.hotword_service import HotwordService
    from sqlalchemy import text

    service = HotwordService()
    channel = "batch_upsert_chan"

    async with service.repo.session_factory() as session:
        await session.execute(
            text("DELETE FROM hot_raw_stats WHERE channel = :channel"),
            {"channel": channel},
        )
        await session.commit()

    await service.repo.save_temp_counts(channel, {"批量写入": {"f": 10.0, "u": 2}})
    await service.repo.save_temp_counts(channel, {"批量写入": {"f": 5.0, "u": 3}})

    data = await service.repo.load_rankings(channel, "_temp")

    assert data["批量写入"]["f"] == 15.0
    assert data["批量写入"]["u"] == 5


@pytest.mark.asyncio
async def test_hotword_suspend_resume():
    from services.hotword_service import HotwordService
    service = HotwordService()
    
    # 初始状态：analyzer 未创建
    assert service._analyzer is None
    
    # 触发分析 -> 创建并激活
    await service.process_batch("test", ["这是一个足够长的测试文本"])
    assert service.analyzer is not None
    assert service.analyzer._jieba is not None
    assert not service.is_suspended
    
    # 手动挂起
    service.suspend()
    assert service.is_suspended
    assert service.analyzer._jieba is None # 内存已释放
    
    # 唤醒
    await service.ensure_active()
    assert not service.is_suspended
    assert service.analyzer._jieba is not None


@pytest.mark.asyncio
async def test_hotword_process_batch_resumes_suspended_state():
    from services.hotword_service import HotwordService
    service = HotwordService()

    await service.process_batch("resume_chan", ["这是一个足够长的测试热词文本"])
    service.suspend()
    assert service.is_suspended
    assert service.analyzer._jieba is None

    await service.process_batch("resume_chan", ["这是另一个足够长的测试热词文本"])

    assert not service.is_suspended
    assert service.analyzer._jieba is not None
