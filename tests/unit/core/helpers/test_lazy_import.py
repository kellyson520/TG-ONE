"""lazy_import 测试 — 惰性模块加载"""
import pytest
from core.helpers.lazy_import import LazyImport


class TestLazyImport:
    """LazyImport 基本功能测试"""

    def test_import_json(self):
        """惰性导入 json 模块"""
        lazy_json = LazyImport("json")
        assert lazy_json._module is None  # 未访问前不加载
        result = lazy_json.dumps({"a": 1})
        assert isinstance(result, str)
        assert lazy_json._module is not None  # 访问后已加载

    def test_import_os(self):
        """惰性导入 os 模块"""
        lazy_os = LazyImport("os")
        assert lazy_os.path is not None

    def test_import_math(self):
        """惰性导入 math 模块"""
        lazy_math = LazyImport("math")
        assert lazy_math.pi == 3.141592653589793

    def test_repr_not_loaded(self):
        """未加载时 repr 显示 not loaded"""
        lazy = LazyImport("json")
        assert "not loaded" in repr(lazy)

    def test_repr_loaded(self):
        """加载后 repr 显示模块信息"""
        lazy = LazyImport("json")
        lazy.dumps  # 触发加载
        r = repr(lazy)
        assert "not loaded" not in r

    def test_dir_proxied(self):
        """dir() 代理到底层模块"""
        lazy_json = LazyImport("json")
        d = dir(lazy_json)
        assert "dumps" in d
        assert "loads" in d

    def test_attribute_error_propagates(self):
        """访问不存在的属性应抛出 AttributeError"""
        lazy_json = LazyImport("json")
        with pytest.raises(AttributeError):
            lazy_json.nonexistent_function

    def test_multiple_accesses_same_module(self):
        """多次访问使用同一模块实例"""
        lazy_json = LazyImport("json")
        m1 = lazy_json._load()
        m2 = lazy_json._load()
        assert m1 is m2

    def test_is_module_type(self):
        """LazyImport 是 ModuleType 子类"""
        import types
        lazy = LazyImport("json")
        assert isinstance(lazy, types.ModuleType)

    def test_module_name_preserved(self):
        """模块名保存在 __name__"""
        lazy = LazyImport("json")
        assert lazy._module_name == "json"
