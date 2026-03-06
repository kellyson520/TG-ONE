import pytest
import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

TEST_HOT_DIR = Path("tests/temp/hot_edge_test")

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
async def test_hotword_edge_cases():
    from services.hotword_service import HotwordService
    service = HotwordService()
    channel = "edge_chan"
    
    # 构建各种极端边界情况的数据
    edge_cases = [
        {"uid": 1, "text": None},                        # 空条目
        {"uid": 2, "text": ""},                          # 空字符串
        {"uid": 3, "text": "   \n  \t   "},              # 全空白符
        {"uid": 4, "text": "https://example.com/a?b=1"}, # 纯链接
        {"uid": 5, "text": "看这个新闻 https://news.com/abcd 真的很棒"}, # 混合链接
        {"uid": 6, "text": "@admin 帮忙处理一下"},         # 混合提及
        {"uid": 7, "text": "/start /help 测试"},           # 混合命令
        {"uid": 8, "text": "a" * 5000}                   # 超长垃圾文本
    ]
    
    # 处理这批异常数据不应崩溃
    await service.process_batch(channel, edge_cases)
    
    # 刷写数据
    await service.flush_to_disk()
    
    ranks = service.get_rankings(channel, period="day")
    words = [r[0] for r in ranks]
    
    # 验证链接、提及、命令是否被成功清理
    for word in words:
        assert "http" not in word
        assert "news.com" not in word
        assert "@" not in word
        assert "/" not in word

@pytest.mark.asyncio
async def test_analyzer_exception_safety():
    from services.hotword_service import HotwordService
    service = HotwordService()
    
    # 采用一个恶意的分词器打入
    await service.analyzer.ensure_engine()
    # 核心更新：现在使用 TF-IDF 提取，需要 Mock extract_tags
    service.analyzer._jieba_tf_idf.extract_tags = MagicMock(side_effect=Exception("Simulated NLP Engine Crash"))
    
    # 处理数据
    await service.process_batch("crash_chan", [{"uid": 9, "text": "这是一条应该触发崩溃的测试文本"}])
    
    # 系统应该捕获异常，并且保证服务不挂掉，l1_cache 不会有脏数据卡住
    assert "crash_chan" not in service.l1_cache or len(service.l1_cache["crash_chan"]) == 0
