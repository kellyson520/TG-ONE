import pytest
import time
from core.cache.wtinylfu import WTinyLFU

def test_wtinylfu_basics():
    cache = WTinyLFU(max_size=10)
    
    # 测试常规写入与读取
    cache["a"] = 1
    assert cache.get("a") == 1
    
    # 填充缓存
    for i in range(10):
        cache[f"key_{i}"] = i
    
    # 此时 "a" 应该由于 window 淘汰进入 main，或者由于频率低被丢弃
    # 这里我们访问 key_0 多次，看它是否能保住
    for _ in range(5):
        cache.get("key_0")
        
    # 添加新项，触发淘汰
    cache["new_key"] = 100
    
    # 验证热点 key 依然存在
    assert cache.get("key_0") == 0

def test_tiny_frequency_admission():
    # max_size=2, window=1 (min), main=1
    cache = WTinyLFU(max_size=2)
    
    # 1. 建立受害者频率
    cache["victim"] = "v"
    for _ in range(5): cache.get("victim") # 频率 = 5
    
    # 2. 放入一个新项
    cache["newcomer"] = "n" 
    
    # 3. 此时 victim 在 main, newcomer 或在 window
    # 再放一个，触发 newcomer (window) -> main 的准入
    # 如果 newcomer 频率低，应该被丢弃，保留 victim
    cache["another"] = "a"
    
    # 由于 newcomer 频率 (0-1) < victim 频率 (5)，newcomer 应该被淘汰
    assert cache.get("victim") == "v"
    assert cache.get("newcomer") is None

if __name__ == "__main__":
    pytest.main([__file__])
