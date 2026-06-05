import pytest
import asyncio
import os
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# 设置测试环境路径
TEST_HOT_DIR = Path("tests/temp/hot_learn_test")

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
    if TEST_HOT_DIR.exists():
        shutil.rmtree(TEST_HOT_DIR)

@pytest.mark.asyncio
async def test_automatic_noise_learning():
    from services.hotword_service import HotwordService
    service = HotwordService()
    channel = "learn_chan"
    
    # 我们要让“某词”成为垃圾词特征。
    # 策略：发送包含已知垃圾标记的消息，并带上“某新词”。
    known_marker = "私聊"
    new_noise_word = "稳赚"
    
    # 模拟 20 条这种消息 (由不同用户发送，增强多样性)
    noise_items = [{"uid": i, "text": f"这个项目真的{new_noise_word}，加我{known_marker}"} for i in range(20)]
    
    # 1. 第一步：处理这些消息
    await service.process_batch(channel, noise_items)
    
    # 2. 第二步：查看 L1 发现池
    assert new_noise_word in service.noise_discovery_l1
    assert service.noise_discovery_l1[new_noise_word] >= 20
    
    # 3. 第三步：执行持久化刷写 —— 新机制下只会合并到累积池，不读磁盘
    await service.flush_to_disk()
    
    # 3.1 验证：候选词已进入累积池
    assert new_noise_word in service._noise_accumulator
    assert service._noise_accumulator[new_noise_word] >= 20
    
    # 4. 强制触发后台学习任务（绕过阈值检查，直接执行）并等待完成
    await service._noise_learning_job()
    
    # 5. 验证：new_noise_word 是否已进入 analyzer 的 noise_markers
    assert new_noise_word in service.analyzer.noise_markers
    
    # 6. 验证：持久化是否成功（现在保存在 DB 中，不再是 JSON 文件）
    saved_noise = await service.repo.load_config("noise")
    assert new_noise_word in saved_noise

@pytest.mark.asyncio
async def test_misidentification_protection():
    from services.hotword_service import HotwordService
    service = HotwordService()
    channel = "protection_chan"
    
    # 正常高频词不应被误判为垃圾特征。
    # 即使它有时出现在包含已知垃圾标记的消息里，只要它在全局正常消息中比例更高。
    known_marker = "私聊"
    common_word = "今天"
    
    # 5条包含标记的消息
    noise_items = [{"uid": i, "text": f"{common_word}天气不错，要买的{known_marker}"} for i in range(100, 105)]
    # 20条正常消息
    normal_items = [{"uid": i, "text": f"{common_word}是个好日子"} for i in range(200, 220)]
    
    await service.process_batch(channel, noise_items)
    await service.process_batch(channel, normal_items)
    
    # 先 flush 合并到累积池，再强制执行学习判定
    # noise_count = 5, total_count = 25 -> ratio = 0.2 < 0.6，不应自动加入
    await service.flush_to_disk()
    await service._noise_learning_job()
    
    assert common_word not in service.analyzer.noise_markers
