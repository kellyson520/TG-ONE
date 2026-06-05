import pytest
from services.network.router import RadixRouter

def test_router_basic_match():
    router = RadixRouter()
    handler = lambda x: x
    router.add_route("main_menu", handler)
    
    match_handler, params = router.match("main_menu")
    assert match_handler == handler
    assert params == {}

def test_router_param_match():
    router = RadixRouter()
    handler = lambda x: x
    router.add_route("rule:{id}:settings", handler)
    
    match_handler, params = router.match("rule:123:settings")
    assert match_handler == handler
    assert params == {"id": "123"}

def test_router_greedy_match():
    router = RadixRouter()
    handler = lambda x: x
    router.add_route("new_menu:{rest}", handler)
    
    # Test 2 parts
    match_handler, params = router.match("new_menu:main")
    assert match_handler == handler
    assert params == {"rest": "main"}
    
    # Test 3 parts (Greedy)
    match_handler, params = router.match("new_menu:toggle_media_type:image")
    assert match_handler == handler
    assert params == {"rest": "toggle_media_type:image"}
    
    # Test many parts
    match_handler, params = router.match("new_menu:a:b:c:d:e")
    assert match_handler == handler
    assert params == {"rest": "a:b:c:d:e"}

def test_router_no_match():
    router = RadixRouter()
    router.add_route("a:b", lambda: None)
    
    match_handler, params = router.match("a:c")
    assert match_handler is None
    assert params == {}
