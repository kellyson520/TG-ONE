import pytest
from services.network.router import RadixRouter

def test_radix_basic():
    """测试基本路由"""
    router = RadixRouter()
    def handler1(): return "h1"
    
    router.add_route("settings", handler1)
    
    h, params = router.match("settings")
    assert h == handler1
    assert params == {}

def test_radix_params():
    """测试路径参数提取"""
    router = RadixRouter()
    def handler_rule(): return "rule"
    
    # 支持 rule:123:edit 这种格式
    router.add_route("rule:{id}:edit", handler_rule)
    
    h, params = router.match("rule:123:edit")
    assert h == handler_rule
    assert params == {"id": "123"}

def test_radix_nested():
    """测试嵌套路由"""
    router = RadixRouter()
    def h_admin(): return "admin"
    def h_cleanup(): return "cleanup"
    
    router.add_route("admin:panel", h_admin)
    router.add_route("admin:cleanup", h_cleanup)
    
    h, _ = router.match("admin:panel")
    assert h == h_admin
    h, _ = router.match("admin:cleanup")
    assert h == h_cleanup

def test_radix_mismatch():
    """测试匹配失败"""
    router = RadixRouter()
    router.add_route("a:b", lambda: None)
    
    h, _ = router.match("a:c")
    assert h is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
