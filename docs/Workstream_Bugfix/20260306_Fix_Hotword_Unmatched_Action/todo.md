# TODO: Fix Hotword Unmatched Action

## Phase 1: Preparation & Planning 📅
- [x] Analyze log and identify root cause
- [x] Create `spec.md`
- [ ] Initialize `process.md` entry

## Phase 2: Implementation 🛠️
- [ ] Create `handlers/button/strategies/hotword.py`
- [ ] Implement `HotwordMenuStrategy` with `match` and `handle`
- [ ] Update `handlers/button/strategies/registry.py` (Add to `HIGH_FREQUENCY_ACTIONS`)
- [ ] Refactor `handlers/button/callback/modules/hotword_callback.py` to use registry

## Phase 3: Verification 🧪
- [ ] Run `python -m py_compile` on modified files
- [ ] Verify registry registration via logs (simulated)
- [ ] Check for any potential circular imports

## Phase 4: Delivery 🚀
- [ ] Create `report.md`
- [ ] Update `version.py` & `CHANGELOG.md`
- [ ] Update `process.md`
- [ ] Git commit & push
