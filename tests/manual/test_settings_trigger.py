
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
sys.path.append(os.path.abspath('.'))

async def test_settings_trigger():
    print("🚀 Starting /settings trigger verification (Mock)...")
    
    # 1. Mock Event
    mock_event = AsyncMock()
    mock_event.sender_id = 12345678
    mock_event.chat_id = 87654321
    mock_event.client = MagicMock()
    mock_event.answer = AsyncMock()
    
    from handlers.button.new_menu_system import new_menu_system
    from controllers.menu_controller import MenuController
    
    # 2. Mock service to avoid DB dependencies
    mock_service = AsyncMock()
    mock_service.get_main_menu_data.return_value = {
        'today': {'total_forwards': 123, 'total_size_bytes': 1024, 'saved_traffic_bytes': 512},
        'dedup': {'cached_signatures': 10}
    }
    
    # 3. Create controller and inject mock service
    ctrl = MenuController()
    ctrl.service = mock_service
    
    # Mock admin controller check_maintenance to avoid more dependencies
    mock_admin_ctrl = AsyncMock()
    mock_admin_ctrl.check_maintenance = AsyncMock()
    
    # We need to mock the import in show_main_menu or monkeypatch it
    import controllers.menu_controller
    # Save original
    original_admin_ctrl_class = controllers.menu_controller.AdminController if hasattr(controllers.menu_controller, 'AdminController') else None
    
    # Use patch-like approach
    class MockAdminController:
        def __init__(self, *args, **kwargs): pass
        async def check_maintenance(self, event): pass
        async def show_analytics_hub(self, event): pass
        async def show_system_hub(self, event): pass
        
    # Since MenuController.show_main_menu does 'from controllers.domain.admin_controller import AdminController'
    # we might need to mock that module
    import controllers.domain.admin_controller
    original_real_admin_ctrl = controllers.domain.admin_controller.AdminController
    controllers.domain.admin_controller.AdminController = MockAdminController
    
    try:
        # Mock _send_menu to verify it's called with right data
        ctrl._send_menu = AsyncMock()
        
        print("执行 show_main_menu...")
        await ctrl.show_main_menu(mock_event)
        
        # Verify
        ctrl._send_menu.assert_called_once()
        args, kwargs = ctrl._send_menu.call_args
        title = args[1]
        text = args[2][0]
        buttons = args[3]
        
        print(f"✅ _send_menu called with title: {title}")
        print(f"✅ Text contains '123 条': {'123 条' in text}")
        print(f"✅ Text contains '10 次': {'10 次' in text}")
        print(f"✅ Buttons count: {len(buttons)}")
        
        if '123 条' in text and len(buttons) > 0:
            print("\n🎊 OVERALL SUCCESS: /settings trigger logic verified successfully.")
        else:
            print("\n❌ VERIFICATION FAILED: Unexpected render output.")
            
    except Exception as e:
        print(f"❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        controllers.domain.admin_controller.AdminController = original_real_admin_ctrl

if __name__ == "__main__":
    asyncio.run(test_settings_trigger())
