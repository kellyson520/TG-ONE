import sys
import pytest
import types
from core.helpers.lazy_import import LazyImport

class TestLazyImport:
    def test_initialization(self):
        """测试 LazyImport 初始化"""
        lazy = LazyImport("json")
        assert lazy._module_name == "json"
        assert lazy._module is None
        # Verify it behaves like a module
        assert isinstance(lazy, types.ModuleType)

    def test_loading_on_access(self):
        """测试访问属性时触发加载"""
        # 使用 standard library 中可能未被频繁使用的库，或者 mock
        # 这里使用 colorsys，通常比较轻量且不一定被加载
        module_name = "colorsys"
        
        # 确保测试前未加载 (如果已被pytest加载则忽略此断言，主要测功能)
        # if module_name in sys.modules:
        #    del sys.modules[module_name]
            
        lazy = LazyImport(module_name)
        assert lazy._module is None
        
        # 触发属性访问
        result = lazy.hsv_to_rgb(0.0, 0.0, 0.0)
        assert result == (0.0, 0.0, 0.0)
        assert lazy._module is not None
        assert lazy._module.__name__ == module_name

    def test_import_error(self):
        """测试导入不存在的模块抛出异常"""
        lazy = LazyImport("non_existent_module_xyz_123_abc")
        with pytest.raises(ImportError):
            _ = lazy.some_attribute

    def test_repr(self):
        """测试 repr 显示状态"""
        lazy = LazyImport("os")
        assert "(not loaded)" in repr(lazy)
        
        _ = lazy.path # Trigger load
        assert "module 'os'" in repr(lazy) or "from" in repr(lazy)

