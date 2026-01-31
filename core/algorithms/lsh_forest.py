
"""
LSH Forest Implementation for SimHash
(Locality Sensitive Hashing Forest)

Rationale:
Although SimHashIndex (Multi-Index Hashing) is great for fixed small Hamming distances (k=3), 
LSH Forest is flexible for variable distance queries and top-k retrieval.
It uses multiple prefix trees (Tries).

However, given the 1GB RAM constraint and Python's object overhead, a full Pointer-based Trie is too heavy.
We will implement key-based "Virtual Tries" using sorted lists or bisect (Prefix Matching).

Structure:
- We generate L different permutations (or hash functions) of the SimHash.
- For each permutation, we store (Permuted_SimHash, Original_ID) in a sorted list.
- To query:
  - We do binary search (bisect) to find the longest common prefix.
  - This simulates navigating a Trie without storing nodes.
  
Reference: Bawa et al., "LSH Forest: Self-Tuning Indexes for Similarity Search"
"""

import bisect
from typing import List, Tuple
import pickle
import os
import logging

# Fallback to standard list functionality since sortedcontainers is not installed
# bisect module works on standard lists

logger = logging.getLogger(__name__)

class LSHForest:
    def __init__(self, num_trees: int = 8, prefix_length: int = 64):
        """
        Args:
            num_trees (l): Number of trees (permutations). Higher = better recall, more memory.
            prefix_length (k): Max prefix length to check.
        """
        self.num_trees = num_trees
        self.prefix_length = prefix_length
        # We store L sorted lists. 
        # Each element is (permuted_hash, doc_id)
        self.trees: List[List[Tuple[int, str]]] = [[] for _ in range(num_trees)]
        self.is_dirty = False
        
        # Precompute permutations? 
        # For simplicity in SimHash, we can just use cyclic shifts or xor masks as "permutations"
        # to avoid storing huge permutation tables.
        
    def _permute(self, val: int, tree_index: int) -> int:
        """
        Generate a 'permutation' of the hash.
        For SimHash (64-bit), a simple cyclic shift or XORing with a salt is efficient.
        We want bits that are usually far apart to be brought together in the prefix.
        
        Simple strategy: Rotate left by (tree_index * step).
        """
        if tree_index == 0:
            return val
        
        # 64-bit rotation
        shift = (tree_index * 7) % 64 # Use prime step
        return ((val << shift) & 0xFFFFFFFFFFFFFFFF) | (val >> (64 - shift))

    def _unpermute(self, val: int, tree_index: int) -> int:
        """Reverse the permutation to recover original hash if needed."""
        if tree_index == 0:
            return val
        shift = (tree_index * 7) % 64
        return ((val >> shift) | (val << (64 - shift))) & 0xFFFFFFFFFFFFFFFF

    def add(self, doc_id: str, simhash: int) -> None:
        """
        Add a document to the index.
        Note: This is O(L * log N) if using insort, or O(L) + lazy sort.
        """
        for i in range(self.num_trees):
            permuted = self._permute(simhash, i)
            # We keep it as tuple (permuted_hash, doc_id)
            # Using standard list and sorting later is often faster for batch loads.
            # For online updates, bisect.insort is ok.
            bisect.insort(self.trees[i], (permuted, doc_id))
        self.is_dirty = True

    def query(self, simhash: int, top_k: int = 10, max_search: int = 100) -> List[str]:
        """
        Query for nearest neighbors.
        
        Strategy:
        1. For each tree, find the insertion point of query hash.
        2. Expand left and right from insertion point.
        3. Check Hamming distance.
        4. Stop early if we inspected `max_search` candidates.
        """
        candidates = set()
        
        # To strictly follow LSH Forest, we should look for longest common prefix.
        # In a sorted list, elements with long common prefix are adjacent.
        
        for i in range(self.num_trees):
            permuted_query = self._permute(simhash, i)
            tree = self.trees[i]
            N = len(tree)
            
            # Binary search
            idx = bisect.bisect_left(tree, (permuted_query, ""))
            
            # Check neighbors (bidirectional expansion)
            # E.g., check idx, idx-1, idx+1, idx-2...
            
            # Limit check count per tree
            checked_in_tree = 0
            
            left, right = idx - 1, idx
            
            while checked_in_tree < (max_search // self.num_trees) + 2:
                # Try right
                if right < N:
                    p_hash, doc_id = tree[right]
                    # Optimization: If prefix mismatch is too large, stop?
                    # For now just collect candidates
                    candidates.add(doc_id)
                    right += 1
                    checked_in_tree += 1
                
                # Try left
                if left >= 0:
                    p_hash, doc_id = tree[left]
                    candidates.add(doc_id)
                    left -= 1
                    checked_in_tree += 1
                    
                if left < 0 and right >= N:
                    break
        
        # Now verify candidates using actual Hamming distance
        # NOTE: We need the ORIGINAL hashes of candidates to compute distance.
        # The index stores (permuted, doc_id). We can re-compute original from permuted.
        
        final_results: List[str] = []
        # We need to retrieve original hash. 
        # Option A: Store (permuted, original, doc_id) -> More memory.
        # Option B: Re-unpermute. -> CPU cost. 
        # Option C: Look up external DB. -> IO cost.
        
        # Let's try to pass 'candidates' to a verifier function if data is external.
        # But if we want self-contained index... let's Unpermute.
        
        # Wait, if we use the set `candidates` which only has doc_id, we can't unpermute.
        # We need to capture (permuted, doc_id, tree_idx) to unpermute.
        
        # Let's change candidates to map: doc_id -> simhash
        candidate_hashes = {}
        
        for i in range(self.num_trees):
            permuted_query = self._permute(simhash, i)
            tree = self.trees[i]
            N = len(tree)
            idx = bisect.bisect_left(tree, (permuted_query, ""))
            
            left, right = idx - 1, idx
            count = 0
            limit = (max_search // self.num_trees) + 2
            
            while count < limit:
                valid_step = False
                if right < N:
                    p_val, d_id = tree[right]
                    if d_id not in candidate_hashes:
                        # Recover original
                        candidate_hashes[d_id] = self._unpermute(p_val, i)
                    right += 1
                    count += 1
                    valid_step = True
                
                if left >= 0 and count < limit:
                    p_val, d_id = tree[left]
                    if d_id not in candidate_hashes:
                        candidate_hashes[d_id] = self._unpermute(p_val, i)
                    left -= 1
                    count += 1
                    valid_step = True
                    
                if not valid_step:
                    break

        # Compute distances
        dist_list = []
        for d_id, d_hash in candidate_hashes.items():
            dist = self._hamming_distance(simhash, d_hash)
            dist_list.append((dist, d_id))
            
        dist_list.sort(key=lambda x: x[0])
        return [uid for dist, uid in dist_list[:top_k]]

    def _hamming_distance(self, f1: int, f2: int) -> int:
        x = f1 ^ f2
        dist = 0
        while x:
            dist += 1
            x &= x - 1
        return dist

    def save(self, filepath: str) -> None:
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(self.trees, f)
            logger.info(f"LSH Forest saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save LSH Forest: {e}")

    def load(self, filepath: str) -> None:
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    self.trees = pickle.load(f)
                logger.info(f"LSH Forest loaded from {filepath}")
            except Exception as e:
                logger.error(f"Failed to load LSH Forest: {e}")

