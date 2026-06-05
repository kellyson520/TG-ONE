"""
Generic Toggle Handler 单元测试
测试通用切换处理逻辑
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from handlers.button.callback.generic_toggle import handle_generic_toggle

@pytest.mark.asyncio
class TestGenericToggleHandler:
    """测试 handle_generic_toggle 处理器"""

    @pytest.fixture
    def mock_event(self):
        event = AsyncMock()
        event.data = b"toggle_enable_rule:1"
        event.answer = AsyncMock()
        event.get_message = AsyncMock()
        return event

    async def test_handle_generic_toggle_success(self, mock_event):
        """测试成功分发到 update_rule_setting"""
        with patch('handlers.button.callback.generic_toggle.update_rule_setting', new_callable=AsyncMock) as mock_update:
            mock_message = AsyncMock()
            mock_event.get_message.return_value = mock_message
            
            await handle_generic_toggle(mock_event)
            
            # 验证 update_rule_setting 被调用，且参数正确
            # toggle_enable_rule 对应 RULE_SETTINGS['enable_rule']，类型为 "rule"
            mock_update.assert_called_once()
            args = mock_update.call_args[0]
            assert args[0] == mock_event
            assert args[1] == "1" # rule_id
            assert args[2] == mock_message
            assert args[3] == "enable_rule" # field_name
            assert args[5] == "rule" # setting_type

    async def test_handle_generic_toggle_format_error(self, mock_event):
        """测试回调数据格式错误"""
        mock_event.data = b"wrong_format"
        await handle_generic_toggle(mock_event)
        mock_event.answer.assert_called_with("回调数据格式错误")

    async def test_handle_generic_toggle_not_found(self, mock_event):
        """测试未找到配置项"""
        mock_event.data = b"toggle_non_existent:1"
        await handle_generic_toggle(mock_event)
        mock_event.answer.assert_called_with("未找到对应的设置项")

    async def test_handle_generic_toggle_no_func(self, mock_event):
        """测试配置项缺少 toggle_func"""
        # change_model 在 AI_SETTINGS 中没有 toggle_func
        mock_event.data = b"change_model:1"
        await handle_generic_toggle(mock_event)
        mock_event.answer.assert_called_with("此设置项不支持切换")

    async def test_handle_generic_toggle_ai_success(self, mock_event):
        """测试 AI 设置的切换分发"""
        with patch('handlers.button.callback.generic_toggle.update_rule_setting', new_callable=AsyncMock) as mock_update:
            mock_event.data = b"toggle_ai:1"
            await handle_generic_toggle(mock_event)
            
            mock_update.assert_called_once()
            args = mock_update.call_args[0]
            assert args[3] == "is_ai" # field_name
            assert args[5] == "ai" # setting_type

    async def test_handle_generic_toggle_exception(self, mock_event):
        """测试发生异常时的处理"""
        # 使用 Mock 对象替代 bytes，以便设置 side_effect
        mock_data = MagicMock()
        mock_data.decode.side_effect = Exception("Decode error")
        mock_event.data = mock_data
        
        await handle_generic_toggle(mock_event)
        mock_event.answer.assert_called_with("操作失败，请检查日志")
