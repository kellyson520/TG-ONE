
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.session_wizard import SessionWizard

class TestSessionWizard:

    @pytest.fixture
    def wizard(self):
        with patch("core.session_wizard.settings") as mock_settings:
            # Mock settings
            mock_settings.SESSION_DIR = MagicMock()
            mock_settings.SESSION_DIR.__truediv__.return_value = MagicMock()
            # Default valid env
            mock_settings.API_ID = 123
            mock_settings.API_HASH = "abc"
            mock_settings.PHONE_NUMBER = "+12345"
            
            wizard = SessionWizard()
            yield wizard

    @pytest.mark.asyncio
    async def test_ensure_session_exists(self, wizard):
        """测试会话存在时直接返回 True"""
        with patch.object(wizard, "_check_env", return_value=True), \
             patch.object(wizard, "_session_exists", return_value=True):
            
            result = await wizard.ensure_session()
            assert result is True

    @pytest.mark.asyncio
    async def test_ensure_session_missing_interactive(self, wizard):
        """测试会话缺失但在交互环境下，启动向导"""
        with patch.object(wizard, "_check_env", return_value=True), \
             patch.object(wizard, "_session_exists", return_value=False), \
             patch("sys.stdin.isatty", return_value=True), \
             patch.object(wizard, "_interactive_login", new_callable=AsyncMock) as mock_login:
            
            mock_login.return_value = True
            
            result = await wizard.ensure_session()
            assert result is True
            mock_login.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_session_missing_non_interactive(self, wizard):
        """测试会话缺失且非交互环境，跳过向导(返回True让主程序尝试报错)"""
        with patch.object(wizard, "_check_env", return_value=True), \
             patch.object(wizard, "_session_exists", return_value=False), \
             patch("sys.stdin.isatty", return_value=False):
            
            result = await wizard.ensure_session()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_env_failure(self, wizard):
        """测试环境变量缺失"""
        with patch("core.session_wizard.settings") as mock_settings:
             mock_settings.API_ID = None # Missing
             
             # Re-init relies on settings import, but we need to patch the check logic usage
             # _check_env reads from imported settings. Since we patched the class wizard fixture, check logic access settings.
             
             # Let's patch settings specifically during the call
             with patch("core.session_wizard.settings", mock_settings):
                 assert wizard._check_env() is False

    @pytest.mark.asyncio
    async def test_interactive_login_flow(self, wizard):
        """测试交互式登录流程 (Mock Telethon)"""
        with patch("core.session_wizard.TelegramClient") as MockClient, \
             patch("builtins.input", side_effect=["12345"]), \
             patch("builtins.print"):
            
            client_instance = MockClient.return_value
            client_instance.connect = AsyncMock()
            client_instance.is_user_authorized = AsyncMock(side_effect=[False, True]) # First false, then true after sign_in
            client_instance.send_code_request = AsyncMock()
            client_instance.sign_in = AsyncMock()
            client_instance.get_me = AsyncMock(return_value=MagicMock(first_name="Test", username="test", id=1))
            client_instance.disconnect = AsyncMock()
            
            result = await wizard._interactive_login()
            
            assert result is True
            client_instance.send_code_request.assert_awaited_once()
            client_instance.sign_in.assert_awaited_once()

