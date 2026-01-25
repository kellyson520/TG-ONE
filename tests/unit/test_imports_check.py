import pytest
import sys
import importlib

def test_critical_module_imports():
    """
    Test that critical modules can be imported without errors (Circular Import checks).
    This test ensures that the refactoring to fix circular imports remains effective.
    """
    modules_to_test = [
        "core.container",
        "listeners.message_listener",
        "listeners.business_handlers",
        "handlers.prompt_handlers",
        "handlers.bot_handler",
        "handlers.command_handlers",
        "handlers.user_handler",
        "handlers.link_handlers",
    ]

    for module_name in modules_to_test:
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
        except Exception as e:
            pytest.fail(f"Failed to import {module_name}: {str(e)}")
