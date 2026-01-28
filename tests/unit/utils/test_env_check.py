import pytest
import asyncio

@pytest.mark.asyncio
async def test_simple_async():
    await asyncio.sleep(0.1)
    assert True
