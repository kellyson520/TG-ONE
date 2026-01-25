
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers.button.new_menu_system import NewMenuSystem
from telethon import Button
import traceback

@pytest.fixture
def mock_event():
    event = AsyncMock()
    event.respond = AsyncMock()
    event.edit = AsyncMock()
    event.answer = AsyncMock()
    event.chat_id = 123456789
    return event

@pytest.fixture
def menu_system():
    return NewMenuSystem()

@patch("handlers.button.base.safe_edit", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_system_hub_navigation(mock_safe_edit, menu_system, mock_event):
    """测试 System Hub -> DB Backup 的导航路径"""
    try:
        # 1. 模拟进入 System Settings (System Hub)
        await menu_system.show_system_settings(mock_event)
        
        # 验证 safe_edit 被调用
        assert mock_safe_edit.called
        args, kwargs = mock_safe_edit.call_args
        text = args[1] if len(args) > 1 else kwargs.get('text', '')
        assert "系统设置" in text
        
        # 2. 模拟点击 数据库备份 -> 进入 show_db_backup_menu
        mock_safe_edit.reset_mock()
        await menu_system.show_db_backup_menu(mock_event)
        
        assert mock_safe_edit.called
        args, _ = mock_safe_edit.call_args
        text = args[1]
        assert "数据库备份" in text
        
    except Exception:
        traceback.print_exc()
        raise

@patch("handlers.button.base.safe_edit", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_module_lazy_loading(mock_safe_edit, menu_system):
    """测试子模块的惰性加载"""
    assert menu_system._system_menu is None
    # 触发加载
    _ = menu_system.system_menu
    assert menu_system._system_menu is not None

@patch("handlers.button.base.safe_edit", new_callable=AsyncMock)
@patch("services.system_service.system_service.backup_database", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_do_backup_integration(mock_backup, mock_safe_edit, menu_system, mock_event):
    """测试执行备份流程"""
    try:
        # Mock backup return
        mock_backup.return_value = {"success": True, "size_mb": 1.5, "path": "/tmp/backup.db"}
        
        await menu_system.do_backup(mock_event)
        
        # 验证是否调用了服务
        assert mock_backup.called
        
        # 验证是否显示了成功信息
        args, _ = mock_safe_edit.call_args
        text = args[1]
        assert "数据库备份成功" in text
        assert "1.50 MB" in text
    except Exception:
        traceback.print_exc()
        raise
