# Task: Upgrade Dedup Algorithms with Elite Implementation

## 1. Background
The current `TG ONE/services/dedup` implementation is a refactored version but lacks some high-performance and high-precision algorithms available in the standalone `engine.py`. This task aims to synchronize and upgrade the system with these advanced features.

## 2. Key Algorithms to Import
- **Numba Optimized Hamming Distance**: Use JIT compilation for 64-bit Hamming distance calculation.
- **Advanced Text Cleaning**: Use `str.maketrans` for high-speed URL, mention, and punctuation stripping.
- **LSH Forest & SimHash v3**: Full integration of semantic similarity search using LSH (Locality Sensitive Hashing) Forest.
- **Tombstone State Management**: Complete integration with the project's Tombstone system for high-efficiency state hibernation.
- **HyperLogLog (HLL)**: Real-time cardinality estimation for unique messages per chat.
- **PCache (Persistent Cache)**: Deep integration with the persistent cache layer for cross-restart hit retention.
- **Background Task Management**: Robust async background processing for expensive video/document hashing.

## 3. Implementation Strategy (Strategy Pattern Preserved)
We will maintain the existing **Strategy Pattern** in `TG ONE/services/dedup` but upgrade the underlying logic in `tools.py` and the strategy implementations.

### 3.1 `tools.py` Enhancements
- Add Numba-based `fast_hamming_64`.
- Add `rapid-fuzz` integration for fine-grained similarity.
- Implement `Hybrid Perceptual Hash v3 (128-bit)`.
- Implement optimized `clean_text_for_hash` using translation tables.

### 3.2 Strategy Upgrades
- **SignatureStrategy**: Enhanced signature generation for documents and photos.
- **VideoStrategy**: Partial hashing, strict feature verification (duration/resolution), and file_id fast-path.
- **ContentStrategy**: V3 Hybrid hash support.
- **SimilarityStrategy**: LSH Forest lookup and SimHash v3 comparison.

### 3.3 Engine (`SmartDeduplicator`) Upgrades
- Automated Tombstone registration.
- LSH Forest index management (chat-level partitioning).
- Config lazy loading and metrics integration.

## 4. Verification Plan
- Run existing `tests/unit/services/test_dedup_service.py`.
- Verify Numba speedup if applicable.
- Check Bloom Filter and HLL metrics in logs.
