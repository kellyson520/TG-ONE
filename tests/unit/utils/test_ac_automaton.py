"""
AC自动机单元测试
"""
import pytest
from utils.processing.ac_automaton import ACAutomaton, ACManager


class TestACAutomaton:
    """测试AC自动机基本功能"""
    
    def test_initialization(self):
        """测试初始化"""
        ac = ACAutomaton()
        assert len(ac.trie) == 1
        assert len(ac.keywords) == 0
        assert not ac.built
    
    def test_add_keyword(self):
        """测试添加关键词"""
        ac = ACAutomaton()
        ac.add_keyword("hello")
        ac.add_keyword("world")
        
        assert len(ac.keywords) == 2
        assert "hello" in ac.keywords
        assert "world" in ac.keywords
    
    def test_build(self):
        """测试构建自动机"""
        ac = ACAutomaton()
        ac.add_keyword("he")
        ac.add_keyword("she")
        ac.add_keyword("his")
        ac.add_keyword("hers")
        
        ac.build()
        assert ac.built
    
    def test_search_single_match(self):
        """测试单个匹配"""
        ac = ACAutomaton()
        ac.add_keyword("hello")
        ac.build()
        
        matches = ac.search("say hello world")
        assert len(matches) == 1
        assert matches[0] == 0  # "hello" 是第0个关键词
    
    def test_search_multiple_matches(self):
        """测试多个匹配"""
        ac = ACAutomaton()
        ac.add_keyword("he")
        ac.add_keyword("she")
        ac.add_keyword("his")
        
        matches = ac.search("she sells his seashells")
        assert len(matches) >= 2  # 至少匹配 "she" 和 "his"
    
    def test_search_overlapping_patterns(self):
        """测试重叠模式"""
        ac = ACAutomaton()
        ac.add_keyword("abc")
        ac.add_keyword("bc")
        ac.add_keyword("c")
        
        matches = ac.search("abc")
        # 应该匹配所有三个模式
        assert len(matches) == 3
    
    def test_has_any_match(self):
        """测试快速匹配检查"""
        ac = ACAutomaton()
        ac.add_keyword("python")
        ac.add_keyword("java")
        ac.build()
        
        assert ac.has_any_match("I love python")
        assert ac.has_any_match("java is good")
        assert not ac.has_any_match("I like rust")
    
    def test_case_sensitivity(self):
        """测试大小写敏感性"""
        ac = ACAutomaton()
        ac.add_keyword("hello")
        ac.build()
        
        # 默认大小写敏感
        assert ac.has_any_match("hello")
        assert not ac.has_any_match("HELLO")
    
    def test_empty_text(self):
        """测试空文本"""
        ac = ACAutomaton()
        ac.add_keyword("test")
        ac.build()
        
        matches = ac.search("")
        assert len(matches) == 0
    
    def test_empty_keywords(self):
        """测试无关键词"""
        ac = ACAutomaton()
        ac.build()
        
        matches = ac.search("any text")
        assert len(matches) == 0
    
    def test_chinese_keywords(self):
        """测试中文关键词"""
        ac = ACAutomaton()
        ac.add_keyword("你好")
        ac.add_keyword("世界")
        ac.build()
        
        matches = ac.search("你好世界")
        assert len(matches) == 2


class TestACManager:
    """测试AC自动机管理器"""
    
    def test_get_automaton(self):
        """测试获取自动机"""
        keywords1 = ["hello", "world"]
        ac1 = ACManager.get_automaton(1, keywords1)
        
        assert ac1 is not None
        assert ac1.built
    
    def test_cache_reuse(self):
        """测试缓存复用"""
        keywords = ["test"]
        ac1 = ACManager.get_automaton(1, keywords)
        ac2 = ACManager.get_automaton(1, keywords)
        
        # 相同规则ID和关键词应返回同一实例
        assert ac1 is ac2
    
    def test_cache_invalidation(self):
        """测试缓存失效"""
        keywords1 = ["old"]
        keywords2 = ["new"]
        
        ac1 = ACManager.get_automaton(1, keywords1)
        ac2 = ACManager.get_automaton(1, keywords2)
        
        # 关键词变化应创建新实例
        assert ac1 is not ac2
    
    def test_clear(self):
        """测试清理"""
        ACManager.get_automaton(1, ["test"])
        ACManager.clear()
        
        # 清理后缓存应为空
        assert len(ACManager._instances) == 0
        assert len(ACManager._keywords_cache) == 0


class TestACPerformance:
    """测试AC自动机性能"""
    
    def test_large_keyword_set(self):
        """测试大量关键词"""
        ac = ACAutomaton()
        
        # 添加1000个关键词
        for i in range(1000):
            ac.add_keyword(f"keyword_{i}")
        
        ac.build()
        
        # 搜索应该很快
        text = "This text contains keyword_500 and keyword_999"
        matches = ac.search(text)
        # Matches: keyword_5, keyword_50, keyword_500, keyword_9, keyword_99, keyword_999
        assert len(matches) == 6
    
    def test_long_text(self):
        """测试长文本"""
        ac = ACAutomaton()
        ac.add_keyword("target")
        ac.build()
        
        # 创建一个很长的文本
        long_text = "word " * 10000 + "target " + "word " * 10000
        matches = ac.search(long_text)
        assert len(matches) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
