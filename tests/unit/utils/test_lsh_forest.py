
import unittest
from core.algorithms.lsh_forest import LSHForest
from core.algorithms.simhash import SimHash

class TestLSHForest(unittest.TestCase):
    def setUp(self):
        self.forest = LSHForest(num_trees=4, prefix_length=64)
        self.simhash = SimHash()

    def test_exact_match(self):
        # Insert some data
        doc1 = "This is a document about testing LSH"
        h1 = self.simhash.build_fingerprint(doc1)
        self.forest.add("doc1", h1)
        
        # Query exactly same hash
        res = self.forest.query(h1, top_k=1)
        self.assertIn("doc1", res)

    def test_near_match(self):
        doc = "Machine learning is fascinating"
        doc_variant = "Machine learning is fasinating" # Typos
        
        h1 = self.simhash.build_fingerprint(doc)
        h2 = self.simhash.build_fingerprint(doc_variant)
        
        # Check actual distance
        dist = SimHash.hamming_distance(h1, h2)
        print(f"Distance: {dist}")
        
        self.forest.add("doc1", h1)
        self.forest.add("noise1", self.simhash.build_fingerprint("Completely different topic"))
        self.forest.add("noise2", self.simhash.build_fingerprint("Another random text"))
        
        # Query with variant
        res = self.forest.query(h2, top_k=3, max_search=50)
        self.assertIn("doc1", res)

    def test_permutation_invertibility(self):
        val = 0x123456789ABCDEF0
        for i in range(8):
            permuted = self.forest._permute(val, i)
            recovered = self.forest._unpermute(permuted, i)
            self.assertEqual(val, recovered, f"Tree {i} permutation failed")

    def test_bulk_performance(self):
        # Insert 1000 items
        data = []
        base_text = "Standard foundation text block "
        target_h = 0
        
        for i in range(1000):
            text = base_text + str(i)
            h = self.simhash.build_fingerprint(text)
            self.forest.add(f"id_{i}", h)
            if i == 500:
                target_h = h
        
        # Query
        results = self.forest.query(target_h, top_k=5)
        self.assertEqual(results[0], "id_500")

    def test_query_logs_malformed_candidate_and_continues(self):
        forest = LSHForest(num_trees=1, prefix_length=64)
        target_h = 0x123456789ABCDEF0
        forest.trees[0] = [
            (target_h, "doc1"),
            (target_h + 1,),
        ]

        with self.assertLogs("core.algorithms.lsh_forest", level="WARNING") as logs:
            results = forest.query(target_h, top_k=1, max_search=10)

        self.assertEqual(results, ["doc1"])
        log_text = "\n".join(logs.output)
        self.assertIn("LSH Forest候选项损坏", log_text)
        self.assertIn("tree=0", log_text)
        self.assertIn("direction=right", log_text)

if __name__ == "__main__":
    unittest.main()
