import hashlib
import re
from typing import List

class SimHash:
    """
    SimHash 算法实现 (纯 Python)
    用于文本相似度检测。
    """

    def __init__(self, f: int = 64):
        """
        Args:
            f: 指纹位数，通常为 64
        """
        self.f = f

    def build_fingerprint(self, text: str) -> int:
        """从文本生成 SimHash 指纹"""
        if not text:
            return 0
        
        # 1. 分词与权重复现 (这里使用简单的 n-gram 或分词)
        features = self._extract_features(text)
        
        # 2. 累加权重位
        v = [0] * self.f
        for feature, weight in features.items():
            h = self._hash(feature)
            for i in range(self.f):
                if (h >> i) & 1:
                    v[i] += weight
                else:
                    v[i] -= weight
                    
        # 3. 降维
        fingerprint = 0
        for i in range(self.f):
            if v[i] > 0:
                fingerprint |= (1 << i)
                
        return fingerprint

    def _hash(self, source: str) -> int:
        """将特征字符串映射为 f 位整数"""
        if source == "":
            return 0
        else:
            x = int(hashlib.md5(source.encode('utf-8')).hexdigest(), 16)
            return x & ((1 << self.f) - 1)

    def _extract_features(self, text: str) -> dict:
        """提取特征及其权重"""
        # 移除非字母数字字符
        text = re.sub(r'[^\w\s]', '', text.lower())
        tokens = text.split()
        
        # 使用 1-gram 和 2-gram 结合以提高短文本稳定性
        features = {}
        # 1-grams
        for token in tokens:
            features[token] = features.get(token, 0) + 1
        # 2-grams
        for i in range(len(tokens) - 1):
            gram = " ".join(tokens[i:i+2])
            features[gram] = features.get(gram, 0) + 1
            
        # 若词数太少，退化到 1-gram
        if not features:
            for token in tokens:
                features[token] = features.get(token, 0) + 1
                
        return features

    @staticmethod
    def hamming_distance(f1: int, f2: int) -> int:
        """计算两个指纹之间的汉明距离"""
        x = f1 ^ f2
        dist = 0
        while x:
            dist += 1
            x &= x - 1
        return dist

    def similarity(self, f1: int, f2: int) -> float:
        """计算相似度 (基于汉明距离)"""
        dist = self.hamming_distance(f1, f2)
        return 1.0 - (dist / self.f)

class SimHashIndex:
    """
    SimHash 索引优化
    使用分段搜索法加速海明距离匹配 (64位分为4段)
    """
    def __init__(self, k: int = 3, f: int = 64):
        """
        Args:
            k: 最大容忍海明距离 (默认 3 为高度相似)
            f: 指纹位数
        """
        self.k = k
        self.f = f
        self.bucket_size = k + 1
        self.buckets = [{} for _ in range(self.bucket_size)]

    def _get_keys(self, val: int) -> List[int]:
        """将指纹分为 k+1 段作为搜索键"""
        keys = []
        bits_per_segment = self.f // self.bucket_size
        mask = (1 << bits_per_segment) - 1
        for i in range(self.bucket_size):
            shift = i * bits_per_segment
            keys.append((val >> shift) & mask)
        return keys

    def add(self, obj_id: str, val: int):
        """添加指纹到索引"""
        keys = self._get_keys(val)
        for i, key in enumerate(keys):
            if key not in self.buckets[i]:
                self.buckets[i][key] = set()
            self.buckets[i][key].add((obj_id, val))

    def search(self, val: int) -> List[str]:
        """搜索相似的内容"""
        keys = self._get_keys(val)
        candidates = set()
        for i, key in enumerate(keys):
            if key in self.buckets[i]:
                candidates.update(self.buckets[i][key])
        
        results = []
        for obj_id, other_val in candidates:
            dist = SimHash.hamming_distance(val, other_val)
            if dist <= self.k:
                results.append(obj_id)
        return results

    def remove(self, obj_id: str, val: int):
        """从索引中移除"""
        keys = self._get_keys(val)
        for i, key in enumerate(keys):
            if key in self.buckets[i]:
                self.buckets[i][key].discard((obj_id, val))
                if not self.buckets[i][key]:
                    del self.buckets[i][key]

# Helper function for backward compatibility and ease of use
def compute_simhash(text: str, f: int = 64) -> int:
    """计算 SimHash 指纹 (快捷函数)"""
    return SimHash(f).build_fingerprint(text)
