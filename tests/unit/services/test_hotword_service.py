import pytest
import asyncio
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

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
    
    from sqlalchemy.ext.asyncio import AsyncSession
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
