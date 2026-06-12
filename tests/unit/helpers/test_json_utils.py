"""json_utils 测试 — dumps/loads 兼容层"""
import pytest
from core.helpers.json_utils import dumps, loads, dumps_bytes, json_dumps, json_loads, JSONDecodeError


class TestDumps:
    """JSON 序列化测试"""

    def test_basic_dict(self):
        result = dumps({"key": "value"})
        assert isinstance(result, str)
        assert '"key"' in result
        assert '"value"' in result

    def test_list(self):
        result = dumps([1, 2, 3])
        assert result == "[1,2,3]"

    def test_nested(self):
        result = dumps({"a": [1, {"b": 2}]})
        assert isinstance(result, str)

    def test_chinese_characters(self):
        """中文字符不转义（ensure_ascii=False）"""
        result = dumps({"name": "测试"})
        assert "测试" in result

    def test_none(self):
        result = dumps(None)
        assert result == "null"

    def test_sort_keys(self):
        result = dumps({"b": 2, "a": 1}, sort_keys=True)
        assert result.index('"a"') < result.index('"b"')


class TestLoads:
    """JSON 反序列化测试"""

    def test_basic(self):
        result = loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_list(self):
        assert loads("[1,2,3]") == [1, 2, 3]

    def test_bytes_input(self):
        result = loads(b'{"x": 1}')
        assert result == {"x": 1}

    def test_invalid_json_raises(self):
        with pytest.raises(JSONDecodeError):
            loads("{invalid}")

    def test_null(self):
        assert loads("null") is None


class TestDumpsBytes:
    """dumps_bytes 测试"""

    def test_returns_bytes(self):
        result = dumps_bytes({"key": "value"})
        assert isinstance(result, bytes)

    def test_decodable(self):
        result = dumps_bytes({"a": 1})
        assert loads(result) == {"a": 1}


class TestAliases:
    """旧代码兼容别名"""

    def test_json_dumps_alias(self):
        assert json_dumps is dumps

    def test_json_loads_alias(self):
        assert json_loads is loads
