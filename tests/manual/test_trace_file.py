import asyncio
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add project root to path
sys.path.append(os.getcwd())

os.environ["LOG_FORMAT"] = "text"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["LOG_COLOR"] = "false"
os.environ["LOG_LANGUAGE"] = "zh"

from core.logging import setup_logging
from core.pipeline import Pipeline, Middleware, MessageContext

from core.config import settings
logger = logging.getLogger("test.trace")

class TestMiddleware(Middleware):
    async def process(self, ctx: MessageContext, next_call):
        logger.info("Step 1: Middleware processing")
        await asyncio.sleep(0.01)
        logger.info("Step 2: Database lookup simulated")
        await next_call()
        logger.info("Step 3: Post-processing finished")

@pytest.mark.asyncio
async def test_trace_file_uses_temp_log_dir(tmp_path, monkeypatch):
    temp_log_dir = Path(tmp_path)
    monkeypatch.setenv("LOG_DIR", str(temp_log_dir))
    monkeypatch.setattr(settings, "LOG_DIR", temp_log_dir)
    monkeypatch.setattr(settings, "LOG_KEY_ONLY", False)
    monkeypatch.setattr(settings, "LOG_BUFFER_SIZE", 1)
    monkeypatch.setattr(settings, "LOG_FLUSH_INTERVAL", 0.0)
    setup_logging()

    pipeline = Pipeline()
    pipeline.add(TestMiddleware())

    ctx = MessageContext(
        client=MagicMock(),
        task_id=1,
        chat_id=123,
        message_id=456,
        message_obj=MagicMock()
    )

    await pipeline.execute(ctx)
    logger.info("Trace verification for %s", trace_id := ctx.metadata["trace_id"])

    for handler in logging.getLogger().handlers:
        flush = getattr(handler, "flush", None)
        if callable(flush):
            flush()

    assert trace_id

    log_file = temp_log_dir / "app.log"
    assert log_file.exists()

    content = log_file.read_text(encoding="utf-8")
    assert trace_id in content
