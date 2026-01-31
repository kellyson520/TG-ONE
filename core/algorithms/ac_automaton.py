import collections
from typing import List, Dict, Set

class ACAutomaton:
    """
    Aho-Corasick 自动机 (纯 Python 实现)
    用于高效地在长文本中查找多个关键词。
    复杂度: 构建 O(sum of keyword lengths), 搜索 O(text length + total matches)
    """

    def __init__(self) -> None:
        # trie[node][char] = next_node
        self.trie: List[Dict[str, int]] = [{}]
        # 失败指针: fail[node] = longest proper suffix node
        self.fail: List[int] = [0]
        # 输出: output[node] = set of keyword indices that end at this node
        self.output: List[Set[int]] = [set()]
        # 关键词列表
        self.keywords: List[str] = []
        # 是否已构建完成
        self.built = False

    def add_keyword(self, keyword: str) -> None:
        """添加一个关键词到字典树"""
        if self.built:
            raise RuntimeError("自动机已构建，无法添加新关键词。若要更新，请创建新实例。")
        
        idx = len(self.keywords)
        self.keywords.append(keyword)
        
        node = 0
        for char in keyword:
            if char not in self.trie[node]:
                self.trie[node][char] = len(self.trie)
                self.trie.append({})
                self.fail.append(0)
                self.output.append(set())
            node = self.trie[node][char]
        
        self.output[node].add(idx)

    def build(self) -> None:
        """构建失败指针 (BFS)"""
        if self.built:
            return
        
        queue: collections.deque[int] = collections.deque()
        
        # 处理第一层子节点
        for char, next_node in self.trie[0].items():
            self.fail[next_node] = 0
            queue.append(next_node)
            
        # 广度优先遍历构建失败指针
        while queue:
            u = queue.popleft()
            for char, v in self.trie[u].items():
                # 找到 v 的失败指针
                f = self.fail[u]
                while char not in self.trie[f] and f != 0:
                    f = self.fail[f]
                
                self.fail[v] = self.trie[f].get(char, 0)
                # 继承失败节点的输出，确保能匹配到子集关键词
                self.output[v].update(self.output[self.fail[v]])
                queue.append(v)
        
        self.built = True

    def search(self, text: str) -> List[int]:
        """
        在文本中搜索所有关键词
        返回匹配到的关键词索引列表
        """
        if not self.built:
            self.build()
        
        node = 0
        matches = set()
        
        for char in text:
            while char not in self.trie[node] and node != 0:
                node = self.fail[node]
            node = self.trie[node].get(char, 0)
            
            if self.output[node]:
                matches.update(self.output[node])
                
        return sorted(list(matches))

    def has_any_match(self, text: str) -> bool:
        """快速判断是否有任何关键词匹配"""
        if not self.built:
            self.build()
        
        node = 0
        for char in text:
            while char not in self.trie[node] and node != 0:
                node = self.fail[node]
            node = self.trie[node].get(char, 0)
            
            if self.output[node]:
                return True
        return False

class ACManager:
    """管理不同规则的 AC 自动机缓存"""
    _instances: Dict[int, ACAutomaton] = {}
    _keywords_cache: Dict[int, List[str]] = {}

    @classmethod
    def get_automaton(cls, rule_id: int, keywords: List[str]) -> ACAutomaton:
        """获取或创建该规则的自动机"""
        # 如果关键词有变化，则重新创建
        if cls._keywords_cache.get(rule_id) != keywords:
            ac = ACAutomaton()
            for kw in keywords:
                if kw: ac.add_keyword(kw)
            ac.build()
            cls._instances[rule_id] = ac
            cls._keywords_cache[rule_id] = keywords
            
        return cls._instances[rule_id]

    @classmethod
    def clear(cls) -> None:
        """清理所有实例"""
        cls._instances = {}
        cls._keywords_cache = {}
