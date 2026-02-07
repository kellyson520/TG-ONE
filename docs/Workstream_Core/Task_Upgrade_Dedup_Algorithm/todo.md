# Todo: Dedup Algorithm Upgrade

## Phase 1: Preparation & Infrastructure (Setup)
- [x] Verify `numba`, `rapidfuzz`, and `xxhash` availability in the environment <!-- id: 0 -->
- [x] Register `SmartDeduplicator` with `tombstone` <!-- id: 1 -->

## Phase 2: Tool Layer Upgrade (Build)
- [x] Implement Numba-optimized `fast_hamming_64` in `tools.py` <!-- id: 2 -->
- [x] Implement optimized `clean_text_for_hash` with translation tables <!-- id: 3 -->
- [x] Upgrade `generate_v3_fingerprint` to 128-bit hybrid hash <!-- id: 4 -->
- [x] Add `calculate_video_partial_file_hash` with multi-seek logic <!-- id: 5 -->

## Phase 3: Strategy Layer Upgrade (Build)
- [x] Enhance `SignatureStrategy` with refined document/photo matching <!-- id: 6 -->
- [x] Upgrade `VideoStrategy` with partial hash + strict verification <!-- id: 7 -->
- [x] Implement LSH Forest search in `SimilarityStrategy` <!-- id: 8 -->
- [x] Integrate PCache into all primary strategies <!-- id: 9 -->

## Phase 4: Engine & Management (Build)
- [x] Update `SmartDeduplicator` facade to orchestrate new components <!-- id: 10 -->
- [x] Add HLL cardinality tracking for unique messages <!-- id: 11 -->
- [x] Add background task management for heavy hashing <!-- id: 12 -->

## Phase 5: Verification & Cleanup (Verify)
- [x] Run `pytest tests/unit/services/test_dedup_service.py` <!-- id: 13 -->
- [x] Check logs for "LSH Forest" and "Bloom Filter" initialization <!-- id: 14 -->
- [x] Generate `report.md` <!-- id: 15 -->

## Phase 6: Release (Report)
- [x] Update `version.py` to 1.2.3.8 <!-- id: 16 -->
- [x] Update `CHANGELOG.md` with V3 upgrade details <!-- id: 17 -->
- [x] Commit changes and tag as `v1.2.3.8` <!-- id: 18 -->
- [x] Push code and tags to repository <!-- id: 19 -->
