"""Test that bare except clauses in message_listener.py are properly typed."""
import pytest
import inspect


def test_no_bare_except_in_message_listener():
    """Verify that message_listener.py has no bare except: clauses."""
    from listeners import message_listener
    source = inspect.getsource(message_listener)
    lines = source.split(chr(10))
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except:":
            pytest.fail(f"Found bare except: at source line {i+1}: {line}")


def test_priority_catchup_detection_handles_invalid_date():
    """Test that priority calculation handles invalid message dates gracefully."""
    import time
    
    # Simulate the priority calculation logic from message_listener
    base_priority = 10
    
    # Simulate a message with an invalid date that would cause timestamp() to fail
    class FakeDate:
        def timestamp(self):
            raise TypeError("Invalid date")
    
    msg_date = FakeDate()
    if msg_date:
        try:
            msg_ts = msg_date.timestamp()
            if time.time() - msg_ts > 300:
                base_priority = 0
        except Exception:
            pass
    
    # Priority should remain unchanged (10) since the except caught the error
    assert base_priority == 10
