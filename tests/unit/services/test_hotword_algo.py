import pytest
import asyncio
import os
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# 设置测试环境路径
TEST_HOT_DIR = Path("tests/temp/hot_algo_test_v2")

@pytest.fixture(autouse=True)
def mock_settings_hot_dir(monkeypatch):
    monkeypatch.setattr("core.config.settings.HOT_DIR", TEST_HOT_DIR)
    monkeypatch.setattr("core.config.settings.HOTWORD_SYNC_INTERVAL", 0.1)
    monkeypatch.setattr("core.config.settings.HOTWORD_BATCH_SIZE", 2)
    monkeypatch.setattr("core.config.settings.HOTWORD_IDLE_TIMEOUT", 1.0)
    
    if TEST_HOT_DIR.exists():
        shutil.rmtree(TEST_HOT_DIR)
    TEST_HOT_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # if TEST_HOT_DIR.exists():
    #    shutil.rmtree(TEST_HOT_DIR)

@pytest.mark.asyncio
async def test_hotword_objectivity_and_burst():
    from services.hotword_service import HotwordService
    service = HotwordService()
    channel = "algo_test_chan"
    
    from models.hotword import HotPeriodStats
    
    # 模拟背景数据 (Month Data) 插入 DB
    curr_month = datetime.now().strftime("%Y%m")
    
    async with service.repo.session_factory() as session:
        m1 = HotPeriodStats(channel=channel, word="消息", period="month", date_key=curr_month, score=3000.0, user_count=1)
        m2 = HotPeriodStats(channel=channel, word="回复", period="month", date_key=curr_month, score=2000.0, user_count=1)
        m3 = HotPeriodStats(channel=channel, word="苹果", period="month", date_key=curr_month, score=30.0, user_count=1)
        session.add_all([m1, m2, m3])
        await session.commit()

    # 1. 测试噪声过滤 (Objectivity)
    # 包含 "优惠", "联系" 等标记的消息应被降权
    garbage_items = [
        {"uid": 101, "text": "全场大优惠，点击私聊联系客服"},
        {"uid": 102, "text": "优惠券点击即领，私聊我"}
    ]
    await service.process_batch(channel, garbage_items)
    await service.flush_to_disk()
    
    ranks = await service.get_rankings(channel, period="day")
    # 验证逻辑不崩溃
    if ranks: pass

    # 2. 测试 Burst & Diversity Detection (真正的热词)
    # 注入今日数据文件到 db (HotRawStats)
    today_data = {
        "消息": {"f": 100.0, "u": 1}, 
        "苹果": {"f": 100.0, "u": 100}
    }
    await service.repo.save_temp_counts(channel, today_data)
        
    # 执行查询
    ranks = await service.get_rankings(channel, period="day")
    
    # 验证排序
    rank_words = [r[0] for r in ranks]
    print(f"Ranks obtained: {rank_words}")
    
    assert "苹果" in rank_words
    assert "消息" in rank_words
    
    apple_idx = rank_words.index("苹果")
    msg_idx = rank_words.index("消息")
    
    # "苹果" 突发性更强，应该排名更靠前 (Index 更小)
    assert apple_idx < msg_idx, f"Burst Detection Failed: Apple {apple_idx}, Msg {msg_idx}"

@pytest.mark.asyncio
async def test_objectivity_penalization():
    from services.hotword_service import HotwordService
    service = HotwordService()
    channel = "noise_chan"
    
    # 正常消息
    await service.process_batch(channel, [
        {"uid": 1, "text": "今天苹果的价格很贵"}, 
        {"uid": 2, "text": "苹果手机发布了"}
    ])
    # 垃圾消息 (包含关键词 "私聊", "联系")
    await service.process_batch(channel, [{"uid": 3, "text": "全场优惠，联系客服私聊"}])
    
    await service.flush_to_disk()
    
    # 检查权重差异
    ranks = await service.get_rankings(channel, period="day")
    rank_map = dict(ranks)
    
    # "苹果" 应该得分较高， "客服" 应该得分非常低 (因为垃圾消息被 0.2 降权且 TF-IDF 权重不同)
    assert rank_map.get("苹果", 0) > rank_map.get("客服", 0)
    print(f"Objectivity weights: {rank_map}")
