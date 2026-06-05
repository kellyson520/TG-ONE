import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from web_admin.fastapi_app import start_web_server, stop_web_server, _server_instance

@pytest.mark.asyncio
async def test_server_shutdown():
    # Mock uvicorn
    with patch('uvicorn.Server') as mock_server_cls:
        mock_server = MagicMock()
        mock_server.serve = AsyncMock()
        mock_server.should_exit = False
        mock_server_cls.return_value = mock_server
        
        # Start server in background task
        task = asyncio.create_task(start_web_server("127.0.0.1", 8000))
        
        # Give it a moment to initialize global instance
        await asyncio.sleep(0.1)
        
        # Verify server instance is set
        from web_admin.fastapi_app import _server_instance
        assert _server_instance == mock_server
        
        # Verify serve was called
        mock_server.serve.assert_called_once()
        
        # Call stop
        await stop_web_server()
        
        # Verify should_exit is set
        assert _server_instance.should_exit is True
        
        # Clean up task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
