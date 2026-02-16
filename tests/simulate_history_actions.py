
import asyncio
import sys
import os
import io

# Set encoding to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
sys.path.append(os.path.abspath(os.curdir))

from handlers.button.strategies.registry import MenuHandlerRegistry
# Import all strategy files to trigger registration
import handlers.button.strategies.history
import handlers.button.strategies.settings
import handlers.button.strategies.rules

async def test_actions():
    # Actions from HistoryModule buttons
    test_actions = [
        "open_wheel_picker",
        "select_days",
        "set_all_time_zero",
        "history_messages",
        "history_filter_media_types",
        "history_toggle_allow_text",
        "history_filter_media_duration",
        "history_message_limit",
        "history_message_filter",
        "history_toggle_image",
        "history_toggle_video",
        "history_toggle_music",
        "history_toggle_voice",
        "history_toggle_document",
        "set_history_limit",
        "custom_history_limit",
        "select_history_task",
        "history_time_range",
        "history_delay_settings",
        "history_quick_stats",
        "history_dry_run",
        "current_history_task",
        "start_history_task",
        "select_task",
        "set_history_delay",
        "confirm_time_range",
        "set_time_range_all",
        "set_time_range_days"
    ]

    print(f"{'Action':<35} | Status")
    print("-" * 50)
    
    unmatched = []
    for action in test_actions:
        matched = False
        for handler in MenuHandlerRegistry._handlers:
            if await handler.match(action):
                print(f"{action:<35} | YES Matched by {handler.__class__.__name__}")
                matched = True
                break
        if not matched:
            print(f"{action:<35} | NO UNMATCHED")
            unmatched.append(action)

    if unmatched:
        print(f"\nTotal Unmatched: {len(unmatched)}")
        print(f"Unmatched actions: {unmatched}")
    else:
        print("\nAll actions successfully matched!")

if __name__ == "__main__":
    asyncio.run(test_actions())
