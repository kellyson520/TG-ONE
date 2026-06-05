"""
Performance Test: AC Automaton Keyword Matching
测试 Aho-Corasick 自动机的关键词匹配性能
"""
import time
import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.algorithms.ac_automaton import ACAutomaton, ACManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_naive_search(keywords, text):
    """朴素搜索算法 (Baseline)"""
    matches = []
    for i, kw in enumerate(keywords):
        if kw.lower() in text.lower():
            matches.append(i)
    return matches

def test_regex_search(keywords, text):
    """正则表达式搜索"""
    pattern = '|'.join(re.escape(kw) for kw in keywords)
    compiled = re.compile(pattern, re.I)
    return bool(compiled.search(text))

def test_ac_automaton_performance():
    """测试 AC 自动机性能"""
    
    logger.info("=" * 60)
    logger.info("Performance Test: AC Automaton Keyword Matching")
    logger.info("=" * 60)
    
    # Generate test data
    keywords = [f"keyword_{i}" for i in range(1000)]
    
    # Test text with some matches
    test_text = "This is a test message with keyword_100 and keyword_500 and some other content " * 10
    
    logger.info(f"\nTest Setup:")
    logger.info(f"Keywords: {len(keywords)}")
    logger.info(f"Text Length: {len(test_text)} chars")
    
    # Test 1: Build AC Automaton
    logger.info(f"\nTest 1: Building AC Automaton")
    start = time.time()
    ac = ACAutomaton()
    for kw in keywords:
        ac.add_keyword(kw)
    ac.build()
    build_time = time.time() - start
    logger.info(f"Build Time: {build_time:.4f}s")
    
    # Test 2: AC Automaton Search
    logger.info(f"\nTest 2: AC Automaton Search (1000 iterations)")
    iterations = 1000
    start = time.time()
    for _ in range(iterations):
        matches = ac.search(test_text.lower())
    ac_time = time.time() - start
    logger.info(f"Total Time: {ac_time:.4f}s")
    logger.info(f"Avg Time per Search: {ac_time/iterations*1000:.4f}ms")
    logger.info(f"Throughput: {iterations/ac_time:.0f} searches/s")
    logger.info(f"Matches Found: {len(matches)}")
    
    # Test 3: Naive Search (Baseline)
    logger.info(f"\nTest 3: Naive Search (1000 iterations)")
    start = time.time()
    for _ in range(iterations):
        matches = test_naive_search(keywords, test_text)
    naive_time = time.time() - start
    logger.info(f"Total Time: {naive_time:.4f}s")
    logger.info(f"Avg Time per Search: {naive_time/iterations*1000:.4f}ms")
    logger.info(f"Throughput: {iterations/naive_time:.0f} searches/s")
    
    # Test 4: Regex Search
    logger.info(f"\nTest 4: Regex Search (1000 iterations)")
    start = time.time()
    for _ in range(iterations):
        result = test_regex_search(keywords, test_text)
    regex_time = time.time() - start
    logger.info(f"Total Time: {regex_time:.4f}s")
    logger.info(f"Avg Time per Search: {regex_time/iterations*1000:.4f}ms")
    logger.info(f"Throughput: {iterations/regex_time:.0f} searches/s")
    
    # Test 5: ACManager (with caching)
    logger.info(f"\nTest 5: ACManager with Caching (1000 iterations)")
    start = time.time()
    for _ in range(iterations):
        ac_cached = ACManager.get_automaton(1, keywords)
        result = ac_cached.has_any_match(test_text.lower())
    manager_time = time.time() - start
    logger.info(f"Total Time: {manager_time:.4f}s")
    logger.info(f"Avg Time per Search: {manager_time/iterations*1000:.4f}ms")
    logger.info(f"Throughput: {iterations/manager_time:.0f} searches/s")
    
    logger.info("\n" + "=" * 60)
    logger.info("Results Summary")
    logger.info("=" * 60)
    logger.info(f"AC Automaton:  {ac_time:.4f}s ({iterations/ac_time:.0f} ops/s)")
    logger.info(f"Naive Search:  {naive_time:.4f}s ({iterations/naive_time:.0f} ops/s)")
    logger.info(f"Regex Search:  {regex_time:.4f}s ({iterations/regex_time:.0f} ops/s)")
    logger.info(f"AC Manager:    {manager_time:.4f}s ({iterations/manager_time:.0f} ops/s)")
    logger.info(f"\nSpeedup vs Naive: {naive_time/ac_time:.2f}x")
    logger.info(f"Speedup vs Regex: {regex_time/ac_time:.2f}x")

if __name__ == "__main__":
    test_ac_automaton_performance()
