import hashlib
import math
from typing import Any

class HyperLogLog:
    """
    HyperLogLog 基数估计算法 (纯 Python 实现)
    用于以极低内存估算亿级独立数据的基数 (Cardinality)。
    """

    def __init__(self, b: int = 10):
        """
        Args:
            b: 指数位，寄存器数量 m = 2^b。
               b=10 (m=1024) 误差约 3%.
               b=14 (m=16384) 误差约 0.8%.
        """
        self.b = b
        self.m = 1 << b
        self.registers = [0] * self.m
        
        # 修正系数
        if self.m == 16: self.alpha = 0.673
        elif self.m == 32: self.alpha = 0.697
        elif self.m == 64: self.alpha = 0.709
        else: self.alpha = 0.7213 / (1 + 1.079 / self.m)

    def _hash(self, item: Any) -> int:
        """使用 SHA256 生成 256 位哈希值"""
        h = hashlib.sha256(str(item).encode('utf-8')).hexdigest()
        return int(h, 16)

    def add(self, item: Any) -> None:
        """添加元素"""
        x = self._hash(item)
        # 前 b 位作为寄存器索引
        idx = x >> (256 - self.b)
        # 剩余位中首个 '1' 出现的位置
        w = x & ((1 << (256 - self.b)) - 1)
        rho = self._get_rho(w, 256 - self.b)
        self.registers[idx] = max(self.registers[idx], rho)

    def _get_rho(self, w: int, max_bits: int) -> int:
        """返回首个 1 出现的位置 (从右往左，1-indexed)"""
        if w == 0:
            return max_bits + 1
        return (w & -w).bit_length() # 这是一个捷径：w & -w 提取最低位的 1

    def count(self) -> int:
        """估算基数"""
        # 调和平均值计算
        z = sum(2.0 ** -r for r in self.registers)
        estimate = self.alpha * (self.m ** 2) / z
        
        # 小基数修正
        if estimate <= 2.5 * self.m:
            v = self.registers.count(0)
            if v > 0:
                estimate = self.m * math.log(self.m / v)
        
        # 大基数修正 (2^256 极其大，通常不触发)
        elif estimate > (1/30) * (2**256):
            estimate = -(2**256) * math.log(1 - estimate / (2**256))
            
        return int(estimate)

class GlobalHLL:
    """全局 HLL 管理器"""
    _instances: dict[str, HyperLogLog] = {}

    @classmethod
    def get_hll(cls, name: str, b: int = 10) -> HyperLogLog:
        if name not in cls._instances:
            cls._instances[name] = HyperLogLog(b=b)
        return cls._instances[name]
