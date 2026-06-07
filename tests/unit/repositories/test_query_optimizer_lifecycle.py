import asyncio
from unittest.mock import AsyncMock

import pytest

from repositories import db_optimization_suite
from repositories import query_optimizer


@pytest.mark.asyncio
async def test_query_optimization_periodic_task_can_be_stopped(monkeypatch):
    prewarm_calls = 0

    async def fake_prewarm_hot_queries():
        nonlocal prewarm_calls
        prewarm_calls += 1

    monkeypatch.setattr(
        query_optimizer.query_prewarmer,
        "prewarm_hot_queries",
        fake_prewarm_hot_queries,
    )

    await query_optimizer.start_query_optimization()
    await asyncio.sleep(0)

    assert prewarm_calls == 1
    assert query_optimizer._periodic_prewarm_task is not None

    await query_optimizer.stop_query_optimization()

    assert query_optimizer._periodic_prewarm_task is None


@pytest.mark.asyncio
async def test_periodic_prewarm_timeout_is_observable(monkeypatch, caplog):
    stop_event = asyncio.Event()
    wait_calls = 0
    prewarm_hot_queries = AsyncMock()

    async def fake_wait_for(awaitable, timeout):
        nonlocal wait_calls
        wait_calls += 1
        if hasattr(awaitable, "close"):
            awaitable.close()
        if wait_calls == 1:
            raise asyncio.TimeoutError
        stop_event.set()
        return True

    monkeypatch.setattr(
        query_optimizer.asyncio,
        "wait_for",
        fake_wait_for,
    )
    monkeypatch.setattr(
        query_optimizer.query_prewarmer,
        "prewarm_hot_queries",
        prewarm_hot_queries,
    )
    caplog.set_level("DEBUG", logger="repositories.query_optimizer")

    await query_optimizer._periodic_prewarm_loop(stop_event)

    assert "Query optimizer periodic prewarm interval elapsed" in caplog.text
    prewarm_hot_queries.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_optimization_suite_stops_query_optimization(
    monkeypatch,
):
    start_query_optimization = AsyncMock()
    stop_query_optimization = AsyncMock()
    monkeypatch.setattr(
        db_optimization_suite,
        "start_query_optimization",
        start_query_optimization,
    )
    monkeypatch.setattr(
        db_optimization_suite,
        "stop_query_optimization",
        stop_query_optimization,
        raising=False,
    )

    suite = db_optimization_suite.DatabaseOptimizationSuite()
    await suite.initialize(
        {
            "enable_monitoring": False,
            "enable_sharding": False,
            "enable_batch_processing": False,
            "enable_index_optimization": False,
        }
    )

    await suite.shutdown()

    start_query_optimization.assert_awaited_once()
    stop_query_optimization.assert_awaited_once()
