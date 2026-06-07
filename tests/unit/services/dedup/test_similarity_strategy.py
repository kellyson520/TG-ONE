from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.dedup.strategies.similarity import SimilarityStrategy
from services.dedup.types import DedupConfig, DedupContext


def build_context(message_text: str, **overrides):
    config = DedupConfig(
        enable_smart_similarity=True,
        min_text_length=1,
        similarity_threshold=0.1,
    )
    ctx = DedupContext(
        message_obj=SimpleNamespace(
            message=message_text,
            text=message_text,
            video=None,
            grouped_id=None,
        ),
        target_chat_id=12345,
        config=config,
        repo=MagicMock(),
        time_window_cache={},
        pcache_repo=MagicMock(),
        bloom_filter=None,
        hll=None,
        bg_tasks=set(),
        logger=MagicMock(),
        content_hash_cache={},
        text_fp_cache={},
        lsh_forests={},
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx


def assert_metric_failure_logged(ctx):
    assert any(
        "相似度指标记录失败" in str(call.args[0])
        for call in ctx.logger.debug.call_args_list
    )


@pytest.mark.asyncio
async def test_lsh_metric_failure_logs_and_keeps_duplicate_result():
    strategy = SimilarityStrategy()
    forest = MagicMock()
    forest.query.return_value = ["doc-1"]
    ctx = build_context(
        "hello world",
        lsh_forests={"12345": forest},
    )

    with patch(
        "services.dedup.strategies.similarity.calculate_simhash",
        return_value=42,
    ), patch(
        "services.dedup.strategies.similarity.DEDUP_FP_HITS_TOTAL.labels",
        side_effect=RuntimeError("metrics down"),
    ):
        result = await strategy.process(ctx)

    assert result.is_duplicate is True
    assert result.algo == "similarity_lsh"
    assert_metric_failure_logged(ctx)


@pytest.mark.asyncio
async def test_memory_hit_metric_failure_logs_and_keeps_duplicate_result():
    strategy = SimilarityStrategy()
    current_fp = 42
    ctx = build_context(
        "hello world",
        text_fp_cache={
            "12345": OrderedDict([(current_fp, {"len": len("hello world")})])
        },
    )

    with patch(
        "services.dedup.strategies.similarity.calculate_simhash",
        return_value=current_fp,
    ), patch(
        "services.dedup.strategies.similarity.DEDUP_HITS_TOTAL.labels",
        side_effect=RuntimeError("metrics down"),
    ):
        result = await strategy.process(ctx)

    assert result.is_duplicate is True
    assert result.algo == "similarity"
    assert_metric_failure_logged(ctx)


@pytest.mark.asyncio
async def test_comparison_metric_failure_logs_and_keeps_miss_result():
    strategy = SimilarityStrategy()
    ctx = build_context(
        "hello world",
        text_fp_cache={
            "12345": OrderedDict([(0, {"len": len("hello world")})])
        },
    )

    with patch(
        "services.dedup.strategies.similarity.calculate_simhash",
        return_value=(2**64 - 1),
    ), patch(
        "services.dedup.strategies.similarity."
        "DEDUP_SIMILARITY_COMPARISONS.observe",
        side_effect=RuntimeError("metrics down"),
    ):
        result = await strategy.process(ctx)

    assert result is None
    assert_metric_failure_logged(ctx)
