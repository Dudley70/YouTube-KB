# TypeScript to Python Conversion + Simplification Plan

**Created**: 2025-11-07 15:00 AEDT  
**Status**: Ready for execution  
**Estimated Time**: 2-3 hours

---

## Decision

**Approach**: Pure Python + Radical Simplification

**Rationale**:
- Code review reveals 90% bloat (see code_review_bloat_analysis.md)
- Core functionality needs ~600-1,500 lines, not 17K
- TypeScript → Python removes Node.js dependency
- Simplification removes unnecessary features

---

## Two-Track Approach

### Track 1: Quick Win (TypeScript → Python Only)
**Time**: 1-2 hours  
**Keep**: All existing bloat  
**Change**: Replace TypeScript with Python equivalent

### Track 2: Recommended (Convert + Simplify)
**Time**: 4-6 hours  
**Change**: Convert TypeScript + Strip bloat to MVP  
**Result**: ~1,500 line clean codebase

**User requested**: Track 1 first, can do Track 2 later if desired

---

## Track 1: TypeScript → Python Conversion

### Files to Create

1. **src/youtube_processor/extractors/deterministic_extractor.py** (~200 lines)
   - Port deterministicExtractor.ts (149 lines)
   - Port utils.ts (115 lines)
   - Port types.ts (45 lines) as dataclasses

### Files to Modify

2. **src/youtube_processor/extractors/deterministic_wrapper.py**
   - Remove subprocess call to Node.js
   - Import and call Python version directly
   - Update tests
### Files to Delete (After validation)

3. **deterministic-extractor/** directory
   - Remove entire TypeScript codebase
   - Remove from git
   - Update .gitignore if needed

### Tests to Update

4. **tests/extractors/**
   - Update imports
   - Verify Python version produces identical output
   - Run full test suite

---

## Implementation Steps

### Step 1: Read TypeScript Implementation ✅
- [x] Read deterministicExtractor.ts
- [x] Read utils.ts  
- [x] Read types.ts
- [x] Understand algorithm

### Step 2: Create Python Version
- [ ] Create deterministic_extractor.py
- [ ] Port utility functions
- [ ] Port main extraction logic
- [ ] Create type definitions (dataclasses)
- [ ] Add docstrings

### Step 3: Update Wrapper
- [ ] Read current deterministic_wrapper.py
- [ ] Replace subprocess call with direct import
- [ ] Update error handling
- [ ] Test with sample transcript

### Step 4: Validation
- [ ] Run existing tests: `pytest tests/extractors/`
- [ ] Compare outputs (TypeScript vs Python)
- [ ] Verify determinism (same input → same output)
- [ ] Check performance

### Step 5: Cleanup
- [ ] Delete deterministic-extractor/ directory
- [ ] Update requirements.txt (remove Node.js mention if any)
- [ ] Update README.md
- [ ] Commit changes

### Step 6: Update Documentation
- [ ] Update PROJECT.md (architecture decision)
- [ ] Update SESSION.md (progress)
- [ ] Update this file (mark complete)

---

## TypeScript Algorithm Summary

### Core Logic
1. **Window splitting**: Split transcript into ~3500 char windows
2. **Sentence extraction**: Split windows into sentences
3. **Candidate scoring**: Score based on:
   - Frequency (40%)
   - Early position (20%)
   - Length normalized (20%)
   - Imperative boost (20%)
4. **Deduplication**: Remove exact duplicates
5. **Near-duplicate collapse**: Jaccard similarity on 3-grams
6. **Ranking**: Sort by score with deterministic tiebreakers
7. **Selection**: Take top N candidates (40-90 based on length)

### Key Functions to Port

**deterministicExtractor.ts**:
- `extractDeterministicUnits()` - Main entry point
- `occurrences()` - Non-overlapping frequency count
- `clamp()` - Clamp number between min/max

**utils.ts**:
- `canonText()` - Normalize text (lowercase, strip punct, NFKC)
- `words()` - Count words
- `splitIntoWindowsByChars()` - Window splitting with sentence boundaries
- `sentenceSplit()` - Regex-based sentence splitter
- `imperativeBoost()` - Detect imperative sentences
- `ngrams3()` - Generate 3-gram set
- `jaccard3()` - Jaccard similarity on 3-grams
- `quant()` - Quantize float for deterministic comparison
- `lex()` - Lexicographic comparison

**types.ts**:
- `Unit` - Candidate unit dataclass
- `ExtractOptions` - Configuration options
- `ExtractResult` - Extraction result with metadata

---

## Python Implementation Notes

### Dependencies Needed
```python
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import List, Set, Optional, Dict, Any
```

### Key Differences
1. **No SHA256 hashing needed** (only for canonicalSerialize, unused)
2. **Unicode normalization**: Use `unicodedata.normalize('NFKC', s)`
3. **Regex**: Python regex is similar but verify patterns
4. **Sorting**: Python tuple comparison works for deterministic sorts

### Determinism Critical Points
1. **Same normalization**: NFKC, lowercase, punct removal
2. **Same sentence splitting**: Exact regex match
3. **Same scoring formula**: No floating point drift
4. **Same tiebreakers**: Quantized score, then window, then start, then lex
5. **Same dedup logic**: Keep earliest by start position

---

## Testing Strategy

### 1. Unit Tests
```bash
pytest tests/extractors/test_deterministic_extractor.py -v
```

### 2. Integration Test
```bash
pytest tests/extractors/test_deterministic_wrapper.py -v
```

### 3. Comparison Test
Create test that:
- Runs TypeScript version (if still available)
- Runs Python version
- Compares output unit-by-unit
- Verifies identical results

### 4. Determinism Test
```bash
# Run twice, verify identical output
python -c "from youtube_processor.extractors.deterministic_extractor import extract_units; \
           result1 = extract_units(transcript); \
           result2 = extract_units(transcript); \
           assert result1 == result2"
```

---

## Acceptance Criteria

- [ ] Pure Python implementation complete
- [ ] All existing tests pass
- [ ] Output identical to TypeScript version (when both exist)
- [ ] Deterministic (same input → same output, always)
- [ ] No Node.js dependency
- [ ] Documentation updated
- [ ] Git commit with clear message

---

## Rollback Plan

If Python version fails:
1. Keep TypeScript version temporarily
2. Debug Python implementation
3. Compare outputs in detail
4. Fix discrepancies
5. Only remove TypeScript after full validation

---

## Future Simplification (Track 2)

After TypeScript → Python conversion succeeds:

### Optional: Create MVP Version
1. Create `youtube_processor_simple/` package
2. Strip out bloat (see code_review_bloat_analysis.md)
3. Keep only:
   - Transcript extraction
   - Deterministic extractor (new Python version)
   - LLM normalization (simplified)
   - Basic CLI (argparse)
   - JSON output
4. ~1,500 lines total
5. Archive bloated version

**Decision**: Can be done in future session if desired

---

**Status**: Ready to begin implementation  
**Next**: Execute Step 2 (Create Python Version)