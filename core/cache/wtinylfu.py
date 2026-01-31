import time
from collections import OrderedDict
from typing import Any, Dict, Tuple, Optional

class CountMinSketch:
    """
    Count-Min Sketch (4-bit version)
    用于近似统计项的访问频率。
    """
    def __init__(self, width: int = 1024, depth: int = 4):
        self.width = width
        self.depth = depth
        self.table = [[0] * width for _ in range(depth)]
        self.count = 0
        self.reset_limit = width * 10  # 达到一定次数后进行老化处理

    def _hash(self, key: Any, seed: int) -> int:
        return hash((key, seed)) % self.width

    def add(self, key: Any) -> None:
        self.count += 1
        for i in range(self.depth):
            idx = self._hash(key, i)
            # 4-bit 饱和计数器 (0-15)
            if self.table[i][idx] < 15:
                self.table[i][idx] += 1
        
        if self.count >= self.reset_limit:
            self._reset()

    def _reset(self) -> None:
        """老化机制：所有计数除以2，防止老数据永久占据高频位"""
        for i in range(self.depth):
            for j in range(self.width):
                self.table[i][j] //= 2
        self.count //= 2

    def estimate(self, key: Any) -> int:
        return min(self.table[i][self._hash(key, i)] for i in range(self.depth))

class WTinyLFU:
    """
    W-TinyLFU 缓存协议实现 (增强版：支持 TTL 和 字典接口)
    结合了 LRU 的新数据敏感度和 LFU 的频率敏感度。
    """
    def __init__(self, max_size: int = 1000, window_ratio: float = 0.01, ttl: Optional[float] = None):
        self.max_size = max_size
        self.window_size = max(1, int(max_size * window_ratio))
        self.main_size = max_size - self.window_size
        self.ttl = ttl
        
        self.window_lru: OrderedDict[Any, Tuple[Any, float]] = OrderedDict()
        self.main_lru: OrderedDict[Any, Tuple[Any, float]] = OrderedDict()
        self.sketch = CountMinSketch()
        
    def _is_expired(self, expiry: float) -> bool:
        if self.ttl is None: return False
        return time.time() > expiry

    def get(self, key: Any, default: Any = None) -> Any:
        # 1. 查 Window LRU
        if key in self.window_lru:
            value, expiry = self.window_lru.pop(key)
            if self._is_expired(expiry):
                return default
            self.window_lru[key] = (value, expiry)
            self.sketch.add(key)
            return value
        
        # 2. 查 Main LRU
        if key in self.main_lru:
            value, expiry = self.main_lru.pop(key)
            if self._is_expired(expiry):
                return default
            self.main_lru[key] = (value, expiry)
            self.sketch.add(key)
            return value
            
        return default

    def __getitem__(self, key: Any) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: Any, value: Any) -> None:
        expiry = time.time() + self.ttl if self.ttl else 0
        
        if key in self.window_lru:
            self.window_lru[key] = (value, expiry)
            self.sketch.add(key)
            return
            
        if key in self.main_lru:
            self.main_lru[key] = (value, expiry)
            self.sketch.add(key)
            return

        # 1. 放入 Window LRU 或 溢出到 Main
        self.sketch.add(key)
        if len(self.window_lru) < self.window_size:
            self.window_lru[key] = (value, expiry)
        else:
            w_key, (w_val, w_exp) = self.window_lru.popitem(last=False)
            self._admit_to_main(w_key, w_val, w_exp)
            self.window_lru[key] = (value, expiry)

    def _admit_to_main(self, key: Any, value: Any, expiry: float) -> None:
        if len(self.main_lru) < self.main_size:
            self.main_lru[key] = (value, expiry)
        else:
            victim_key, (victim_val, victim_exp) = self.main_lru.popitem(last=False)
            
            # 如果候选者过期，直接替换
            if self._is_expired(victim_exp):
                self.main_lru[key] = (value, expiry)
                return

            key_freq = self.sketch.estimate(key)
            victim_freq = self.sketch.estimate(victim_key)
            
            if key_freq > victim_freq:
                self.main_lru[key] = (value, expiry)
            else:
                self.main_lru[victim_key] = (victim_val, victim_exp)

    def __contains__(self, key: Any) -> bool:
        return self.get(key) is not None

    def __delitem__(self, key: Any) -> None:
        if key in self.window_lru:
            del self.window_lru[key]
        elif key in self.main_lru:
            del self.main_lru[key]

    def clear(self) -> None:
        self.window_lru.clear()
        self.main_lru.clear()
        self.sketch = CountMinSketch()
