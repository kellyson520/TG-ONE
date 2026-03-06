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
    
    temp_file = TEST_HOT_DIR / channel / f"{channel}_temp.json"
    assert temp_file.exists()
    
    # 3. 测试排行榜查询 (实时查询会回退到 temp)
    ranks = service.get_rankings(channel, period="day")
    assert len(ranks) > 0
    # 验证排序：第一个权重应该最大
    assert ranks[0][1] >= ranks[-1][1]

    # 4. 测试模糊匹配
    matches = service.fuzzy_match_channel("test")
    assert channel in matches

@pytest.mark.asyncio
async def test_hotword_aggregation():
    from services.hotword_service import HotwordService
    service = HotwordService()
    channel = "agg_chan"
    
    # 模拟昨天的日报数据
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    chan_dir = TEST_HOT_DIR / channel
    chan_dir.mkdir(parents=True, exist_ok=True)
    
    # 准备 temp 文件
    temp_file = chan_dir / f"{channel}_temp.json"
    import json
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump({"测试": 10, "聚合": 5}, f)
        
    # 执行每日聚合
    await service.aggregate_daily()
    
    # 检查 temp 是否消失，day 文件是否生成
    day_file = chan_dir / f"{channel}_day_{yesterday}.json"
    assert not temp_file.exists()
    assert day_file.exists()
    
    # 5. 测试月度聚合
    # 手动创建两个日文件
    curr_month = datetime.now().strftime("%Y%m")
    day1 = chan_dir / f"{channel}_day_{curr_month}01.json"
    day2 = chan_dir / f"{channel}_day_{curr_month}02.json"
    with open(day1, 'w', encoding='utf-8') as f: json.dump({"月": 1}, f)
    with open(day2, 'w', encoding='utf-8') as f: json.dump({"月": 2}, f)
    
    # 下个月初执行上月聚合测试比较复杂，这里直接模拟
    with patch('services.hotword_service.datetime') as mock_date:
        # 模拟为下个月 1 号
        mock_date.now.return_value = datetime.now() + timedelta(days=32)
        mock_date.strftime = datetime.strftime
        await service.aggregate_monthly()
    
    month_file = chan_dir / f"month_{curr_month}.json"
    assert month_file.exists()
    with open(month_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data["月"] == 3

@pytest.mark.asyncio
async def test_hotword_suspend_resume():
    from services.hotword_service import HotwordService
    service = HotwordService()
    
    # 初始状态：analyzer 未创建
    assert service._analyzer is None
    
    # 触发分析 -> 创建并激活
    await service.process_batch("test", ["测试"])
    assert service._analyzer is not None
    assert service._analyzer._jieba is not None
    assert not service.is_suspended
    
    # 手动挂起
    service.suspend()
    assert service.is_suspended
    assert service._analyzer._jieba is None # 内存已释放
    
    # 唤醒
    await service.ensure_active()
    assert not service.is_suspended
    assert service._analyzer._jieba is not None
