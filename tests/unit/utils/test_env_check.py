import pytest
import asyncio
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_simple_async():
    await asyncio.sleep(0.1)
    assert True
