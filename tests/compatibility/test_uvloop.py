import pytest
import asyncio
import platform
import os

# Windows does not support uvloop
@pytest.mark.skipif(platform.system() == 'Windows', reason="uvloop not supported on Windows")
@pytest.mark.skipif(os.environ.get("DISABLE_UVLOOP") == "true", reason="uvloop disabled via env")
async def test_uvloop_compatibility():
    """
    Test basic compatibility of uvloop if installed.
    This test attempts to import uvloop and verify it can be set as the policy.
    """
    try:
        import uvloop
    except ImportError:
        pytest.skip("uvloop not installed")

    # Verify we can set the policy
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    assert isinstance(loop, uvloop.Loop)
    
    # Test simple async operation
    async def sleep_task():
        await asyncio.sleep(0.01)
        return True
    
    result = loop.run_until_complete(sleep_task())
    assert result is True
    
    loop.close()

@pytest.mark.skipif(platform.system() == 'Windows', reason="uvloop not supported on Windows")
async def test_sqlalchemy_uvloop_compat():
    """
    Test SQLAlchemy Async engine compatibility with uvloop
    """
    try:
        import uvloop
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
    except ImportError:
        pytest.skip("uvloop or sqlalchemy not installed")

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    
    # Use in-memory SQLite for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
        
    await engine.dispose()
