import pytest
import json
from core.helpers import json_utils


class TestDumps:
    def test_basic_dict(self):
        result = json_utils.dumps({"a": 1})
        assert '"a"' in result
        assert '1' in result

    def test_list(self):
        result = json_utils.dumps([1, 2, 3])
        assert result == "[1,2,3]"

    def test_string(self):
        result = json_utils.dumps("hello")
        assert result == '"hello"'

    def test_none(self):
        result = json_utils.dumps(None)
        assert result == "null"

    def test_nested(self):
        result = json_utils.dumps({"a": {"b": [1, 2]}})
        assert '"b"' in result

    def test_sort_keys(self):
        result = json_utils.dumps({"b": 2, "a": 1}, sort_keys=True)
        keys = list(json.loads(result).keys())
        assert keys == ["a", "b"]

    def test_ensure_ascii_false(self):
        result = json_utils.dumps({"k": "中文"})
        assert "中文" in result


class TestLoads:
    def test_basic(self):
        assert json_utils.loads('{"a": 1}') == {"a": 1}

    def test_list(self):
        assert json_utils.loads("[1,2,3]") == [1, 2, 3]

    def test_bytes_input(self):
        assert json_utils.loads(b'{"x": true}') == {"x": True}

    def test_invalid_raises(self):
        with pytest.raises(json_utils.JSONDecodeError):
            json_utils.loads("{invalid}")


class TestDumpsBytes:
    def test_returns_bytes(self):
        result = json_utils.dumps_bytes({"a": 1})
        assert isinstance(result, bytes)

    def test_content_matches(self):
        result = json_utils.dumps_bytes([1, 2])
        assert json.loads(result) == [1, 2]
