"""
惰性加载工具 (Lazy Import Utility)
================================
提供一个健壮的 LazyImport 类，用于推迟重型模块的加载，直到它们被实际访问时。
这可以显著提高启动速度，并减少未使用的功能路径的内存占用。

用法:
    from core.helpers.lazy_import import LazyImport
    
    # 定义模块级惰性导入
    np = LazyImport("numpy")
    
    def process_data(data):
        # 仅在此处（首次访问时）导入 numpy
        return np.array(data)

"""
import importlib
import types
from typing import Any, Optional

class LazyImport(types.ModuleType):
    """
    当访问属性时惰性导入模块。
    
    此类代理对底层模块的属性访问，仅在必要时才导入它。
    """
    def __init__(self, module_name: str, package: Optional[str] = None):
        """
        初始化 LazyImport 代理。
        
        Args:
            module_name: 要导入的模块名称 (例如 "numpy", ".utils")
            package: 用于相对导入的包名称 (可选)
        """
        super().__init__(module_name)
        self._module_name = module_name
        self._package = package
        self._module = None

    def _load(self) -> types.ModuleType:
        """如果尚未导入，则导入模块。"""
        if self._module is None:
            self._module = importlib.import_module(self._module_name, package=self._package)
        return self._module

    def __getattr__(self, name: str) -> Any:
        """代理对底层模块的属性访问。"""
        module = self._load()
        return getattr(module, name)

    def __dir__(self):
        """代理 dir() 到底层模块。"""
        module = self._load()
        return dir(module)

    def __repr__(self):
        if self._module:
            return repr(self._module)
        return f"<LazyImport: {self._module_name} (not loaded)>"
