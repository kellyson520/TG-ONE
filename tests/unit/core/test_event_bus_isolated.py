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
