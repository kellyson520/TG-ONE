import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from core.aop import audit_log
from core.context import user_id_var, username_var, ip_address_var

# Mock Service Class
class MockService:
    @audit_log(action="TEST_ACTION", resource_type="TEST_RES")
    async def sensitive_op(self, arg1, arg2, user_id=None):
        return f"{arg1}-{arg2}"

    @audit_log(action="FAILING_ACTION", resource_type="TEST_RES")
    async def failing_op(self):
        raise ValueError("Oops")

@pytest.mark.asyncio
async def test_audit_log_success():
    # Setup Context
    token_uid = user_id_var.set(999)
    token_user = username_var.set("admin_test")
    token_ip = ip_address_var.set("1.2.3.4")
    
    service = MockService()
    
    try:
        # Patch audit_service
        with patch("services.audit_service.audit_service") as mock_audit:
            mock_audit.log_event = AsyncMock()
            
            # Execute
            result = await service.sensitive_op("hello", "world", user_id=888)
            
            # Verify result
            assert result == "hello-world"
            
            # Wait for async task (fire and forget)
            # In unit test environment, create_task might need a sleep to ensure it runs
            await asyncio.sleep(0.01)
            
            # Verify Log Call
            mock_audit.log_event.assert_called_once()
            call_kwargs = mock_audit.log_event.call_args.kwargs
            
            assert call_kwargs["action"] == "TEST_ACTION"
            assert call_kwargs["user_id"] == 999
            assert call_kwargs["username"] == "admin_test"
            assert call_kwargs["status"] == "success"
            assert call_kwargs["resource_id"] == "888" # Extracted from kwargs
            
    finally:
        user_id_var.reset(token_uid)
        username_var.reset(token_user)
        ip_address_var.reset(token_ip)

@pytest.mark.asyncio
async def test_audit_log_failure():
    service = MockService()
    
    with patch("services.audit_service.audit_service") as mock_audit:
        mock_audit.log_event = AsyncMock()
        
        # Execute expecting error
        with pytest.raises(ValueError):
            await service.failing_op()
            
        await asyncio.sleep(0.01)
        
        # Verify Log Call
        mock_audit.log_event.assert_called_once()
        call_kwargs = mock_audit.log_event.call_args.kwargs
        
        assert call_kwargs["action"] == "FAILING_ACTION"
        assert call_kwargs["status"] == "failure"
        assert "Oops" in call_kwargs["details"]["error"]
