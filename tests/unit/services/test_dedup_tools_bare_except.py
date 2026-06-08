"""Test that bare except clauses in dedup/tools.py are properly typed."""
import pytest
import math


def test_get_size_bucket_handles_negative():
    """get_size_bucket should return 0 for negative sizes."""
    from services.dedup.tools import get_size_bucket
    assert get_size_bucket(-1) == 0
    assert get_size_bucket(0) == 0


def test_get_size_bucket_handles_valid():
    """get_size_bucket should compute correctly for valid sizes."""
    from services.dedup.tools import get_size_bucket
    assert get_size_bucket(1) == 0
    assert get_size_bucket(256) == 64
    assert get_size_bucket(2**40) == 255


def test_extract_stream_vector_returns_int():
    """extract_stream_vector should return an integer for valid docs."""
    from services.dedup.tools import extract_stream_vector
    
    class FakeDoc:
        w = 1920
        h = 1080
    
    result = extract_stream_vector(FakeDoc())
    assert isinstance(result, int)
    assert result == ((1920 & 0xFFFF) << 16) | (1080 & 0xFFFF)


def test_extract_stream_vector_handles_none_attrs():
    """extract_stream_vector should return 0 when attrs are missing."""
    from services.dedup.tools import extract_stream_vector
    
    class EmptyDoc:
        pass
    
    result = extract_stream_vector(EmptyDoc())
    assert result == 0


def test_bare_except_replaced_with_typed():
    """Verify that the source file has no bare except: clauses."""
    import inspect
    from services.dedup import tools
    source = inspect.getsource(tools)
    lines = source.split(chr(10))
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except:":
            pytest.fail(f"Found bare except: at source line {i+1}: {line}")
