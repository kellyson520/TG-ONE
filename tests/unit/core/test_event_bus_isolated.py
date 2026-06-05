import pytest
import asyncio
from core.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_basic():
    bus = EventBus()
    received = []
    
    async def handler(data):
        received.append(data)
        
    bus.subscribe("test", handler)
    await bus.publish("test", {"foo": "bar"}, wait=True)
    
    assert len(received) == 1
    assert received[0]["foo"] == "bar"


@pytest.mark.asyncio
async def test_event_bus_wildcard():
    bus = EventBus()
    received = []
    
    async def handler(data):
        received.append(data)
        
    bus.subscribe("*", handler)
    await bus.publish("any_event", "data", wait=True)
    
    assert len(received) == 1
    assert received[0] == "data"


@pytest.mark.asyncio
async def test_event_bus_safe_execute():
    bus = EventBus()
    
    async def failing_handler(data):
        raise ValueError("Boom")
        
    bus.subscribe("test", failing_handler)
    
    # should not raise even if wait=False (default)
    await bus.publish("test", "data")
    await asyncio.sleep(0.1) # wait for task


@pytest.mark.asyncio
async def test_event_bus_skips_broadcast_task_without_broadcaster(monkeypatch):
    bus = EventBus()
    created_tasks = 0

    def fake_create_task(coro, *args, **kwargs):
        nonlocal created_tasks
        created_tasks += 1
        coro.close()
        raise AssertionError("create_task should not be called without broadcaster")

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    await bus.publish("no_listeners", "data")

    assert created_tasks == 0


@pytest.mark.asyncio
async def test_event_bus_accepts_callable_listener_instances():
    bus = EventBus()
    received = []

    class Listener:
        def __call__(self, data):
            received.append(data)

    bus.subscribe("test", Listener())
    await bus.publish("test", "data", wait=True)

    assert received == ["data"]
