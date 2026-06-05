import pytest
from fastapi import Request, HTTPException
from web_admin.security.csrf import validate_csrf, CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from starlette.datastructures import Headers, FormData
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
class TestCSRFValidation:
    
    def create_mock_request(self, method="POST", cookies=None, headers=None, form_data=None):
        request = MagicMock(spec=Request)
        request.method = method
        request.cookies = cookies or {}
        request.headers = Headers(headers or {})
        request.scope = {}
        
        if form_data:
            request.form = AsyncMock(return_value=FormData(form_data))
        else:
            request.form = AsyncMock(return_value=FormData())
            
        return request

    async def test_safe_methods_bypass(self):
        # GET 请求应自动通过
        request = self.create_mock_request(method="GET")
        await validate_csrf(request) # 不应抛出异常

    async def test_missing_cookie(self):
        # 缺少 Cookie
        request = self.create_mock_request(method="POST")
        with pytest.raises(HTTPException) as exc:
            await validate_csrf(request)
        assert exc.value.status_code == 403
        assert "Cookie Missing" in exc.value.detail

    async def test_header_validation_success(self):
        token = "test-token"
        request = self.create_mock_request(
            method="POST",
            cookies={CSRF_COOKIE_NAME: token},
            headers={CSRF_HEADER_NAME: token}
        )
        await validate_csrf(request) # 应通过

    async def test_form_validation_success(self):
        token = "test-token"
        request = self.create_mock_request(
            method="POST",
            cookies={CSRF_COOKIE_NAME: token},
            headers={"content-type": "application/x-www-form-urlencoded"},
            form_data={"csrf_token": token}
        )
        await validate_csrf(request) # 应通过

    async def test_token_mismatch(self):
        request = self.create_mock_request(
            method="POST",
            cookies={CSRF_COOKIE_NAME: "token-a"},
            headers={CSRF_HEADER_NAME: "token-b"}
        )
        with pytest.raises(HTTPException) as exc:
            await validate_csrf(request)
        assert exc.value.status_code == 403
        assert "Verification Failed" in exc.value.detail

    async def test_new_token_in_scope(self):
        # 兼容中间件刚生成 Token 的场景
        token = "new-token"
        request = self.create_mock_request(method="POST", headers={CSRF_HEADER_NAME: token})
        request.scope["csrf_token_new"] = token
        await validate_csrf(request) # 应通过
