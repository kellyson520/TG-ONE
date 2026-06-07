import asyncio

import pytest

from services.network.timing_wheel import HashedTimingWheel


def test_timing_wheel_rounds_fractional_delay_up_to_next_tick():
    tw = HashedTimingWheel(tick_ms=100, slots=10)

    async def task_cb():
        return None

    tw.add_task("fractional", 0.15, task_cb)

    scheduled_slots = [
        idx
        for idx, slot in enumerate(tw.wheel)
        if any(task.task_id == "fractional" for task in slot)
    ]
    assert scheduled_slots == [2]


@pytest.mark.asyncio
async def test_timing_wheel_does_not_tick_when_empty(monkeypatch):
    tw = HashedTimingWheel(tick_ms=10, slots=10)
    original_sleep = asyncio.sleep
    sleep_calls = 0

    async def fake_sleep(delay):
        nonlocal sleep_calls
        sleep_calls += 1
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "services.network.timing_wheel.asyncio.sleep",
        fake_sleep,
    )

    await tw.start()
    try:
        await original_sleep(0)
        assert sleep_calls == 0
    finally:
        await tw.stop()


@pytest.mark.asyncio
async def test_timing_wheel_execution():
    tw = HashedTimingWheel(tick_ms=100, slots=10)
    await tw.start()

    results = []

    async def task_cb(val):
        results.append(val)

    tw.add_task("t1", 0.3, task_cb, "hello")
    tw.add_task("t2", 1.2, task_cb, "world")

    await asyncio.sleep(0.5)
    assert "hello" in results
    assert "world" not in results

    await asyncio.sleep(1.0)
    assert "world" in results

    await tw.stop()


@pytest.mark.asyncio
async def test_timing_wheel_cancellation():
    tw = HashedTimingWheel(tick_ms=100, slots=10)
    await tw.start()

    results = []

    async def task_cb():
        results.append(1)

    tw.add_task("cancel_me", 0.5, task_cb)
    tw.cancel_task("cancel_me")

    await asyncio.sleep(0.8)
    assert len(results) == 0

    await tw.stop()


@pytest.mark.asyncio
async def test_timing_wheel_replacing_same_task_id_cancels_old_slot_entry():
    tw = HashedTimingWheel(tick_ms=50, slots=10)
    await tw.start()

    results = []

    async def task_cb(val):
        results.append(val)

    tw.add_task("same", 0.1, task_cb, "old")
    tw.add_task("same", 0.3, task_cb, "new")

    await asyncio.sleep(0.2)
    assert results == []

    await asyncio.sleep(0.25)
    assert results == ["new"]

    await tw.stop()


if __name__ == "__main__":
    asyncio.run(test_timing_wheel_execution())
