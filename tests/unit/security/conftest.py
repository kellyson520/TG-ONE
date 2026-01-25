"""
Security 测试专用 conftest.py
确保 web_admin.security 模块可以正确导入
"""
import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 清除可能被污染的模块缓存
modules_to_clear = [
    'web_admin',
    'web_admin.security',
    'web_admin.security.rate_limiter',
    'web_admin.security.password_validator',
    'web_admin.security.csrf',
]

for mod in modules_to_clear:
    if mod in sys.modules:
        del sys.modules[mod]

# 不需要额外的 fixtures，使用父级 conftest.py 的
