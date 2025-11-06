# Phase A Validation Checklist

## Purpose

Systematically validates each component of Phase A pipeline with:
- ✅ Clear pass/fail for each checkpoint
- 📝 Detailed findings logged
- 🔍 Specific error messages
- 💾 Results saved to file

## Checkpoints

### 1. Environment Setup
- Python version (3.8+)
- Anthropic API key set
- Working directory valid

### 2. Module Imports
- TranscriptExtractor
- DeterministicExtractor (deterministic_wrapper)
- TranscriptAnalyzer

### 3. Transcript Extraction
- TranscriptExtractor initializes
- Transcript extracted (>100 words)

### 4. Deterministic Extraction
- DeterministicExtractor initializes
- Candidates extracted (10+)
- Result structure valid (dict with 'units' key)
- Candidate structure valid (has 'id' and 'text')

### 5. LLM Normalizer Setup
- TranscriptAnalyzer initializes
- Has analyze_units method

### 6. LLM Normalization
- Normalizes 3 candidates (fast test)
- Returns matching count
- Valid unit structure
- Detects fallback mode (all unclear = fail)
- Shows sample results

### 7. Determinism Test
- Runs normalization twice
- Same count
- Same IDs
- Same types (100% = cache working)

## How to Run

```bash
export ANTHROPIC_API_KEY="your-key"
cd "/Users/dudley/Projects/YouTube Extractions/youtube-processor"
python3 tests/phase_a_live_test/validate_checklist.py
```

## Expected Output (Success)

```
================================================================================
  PHASE A VALIDATION CHECKLIST
================================================================================
Time: 2025-11-06 21:00:00

================================================================================
  CHECKPOINT 1: Environment Setup
================================================================================
✅ Python version: 3.9.6
✅ Anthropic API key set
✅ Working directory: /Users/dudley/Projects/YouTube Extractions/youtube-processor

================================================================================
  CHECKPOINT 2: Module Imports
================================================================================
✅ TranscriptExtractor import
✅ DeterministicExtractor import
✅ TranscriptAnalyzer import

================================================================================
  CHECKPOINT 3: Transcript Extraction
================================================================================
✅ TranscriptExtractor initialized
   Extracting video: aA9KP7QIQvM ...
✅ Transcript extracted: 7,153 words

================================================================================
  CHECKPOINT 4: Deterministic Extraction
================================================================================
✅ DeterministicExtractor initialized
   Extracting from 47632 char transcript ...
✅ Result type: dict
✅ Result has 'units' key
✅ Candidates extracted: 40
✅ Candidate structure valid
   Sample ID: 0:363-468
   Sample text: The real question is, what types of work can Haiku...

================================================================================
  CHECKPOINT 5: LLM Normalizer Setup
================================================================================
✅ TranscriptAnalyzer initialized
✅ Analyzer has analyze_units method

================================================================================
  CHECKPOINT 6: LLM Normalization (3 Candidates)
================================================================================
   Testing with 3 candidates
   This may take 20-30 seconds...
✅ analyze_units completed
✅ Result has knowledge_units
✅ Unit count: 3 (expected 3)
✅ Unit structure valid
✅ Normalization quality: All units properly categorized

   Sample results:
   1. [technique] Performance Comparison Method
   2. [observation] Multi-Agent Speed Difference
   3. [pattern] Tool Call Frequency Analysis

================================================================================
  CHECKPOINT 7: Determinism Test
================================================================================
   Running normalization again to test cache...
✅ Determinism: Count matches (3)
✅ Determinism: IDs match (3/3)
✅ Determinism: Types match (3/3)

================================================================================
  VALIDATION SUMMARY
================================================================================

FINDINGS:
  1. Python 3.9.6: OK
  2. API key: SET (89 chars)
  3. Working dir: OK
  4. TranscriptExtractor: OK
  5. DeterministicExtractor: OK
  6. TranscriptAnalyzer: OK
  7. TranscriptExtractor init: OK
  8. Transcript: 7153 words
  9. DeterministicExtractor init: OK
  10. Candidates: 40 units
  11. Candidate structure: OK
  12. TranscriptAnalyzer init: OK
  13. Analyzer API: OK
  14. Unit structure: OK
  15. Quality: SUCCESS (0 fallback)
  16. Determinism: 100% (3/3 match)

✅ ALL CHECKPOINTS PASSED

Next steps:
  1. Test with more candidates (10, 20, 40)
  2. Measure actual costs
  3. Deploy to production pipeline

================================================================================

📝 Findings saved to: output/validation_20251106_210015.txt
```

## Expected Output (Fallback Mode)

```
================================================================================
  CHECKPOINT 6: LLM Normalization (3 Candidates)
================================================================================
   Testing with 3 candidates
   This may take 20-30 seconds...
✅ analyze_units completed
✅ Result has knowledge_units
✅ Unit count: 3 (expected 3)
✅ Unit structure valid
❌ Normalization quality
   ALL units in fallback mode - LLM call failed
   Possible causes:
     - Invalid API key
     - Rate limit hit
     - Network timeout
     - LLM returned invalid JSON

   Sample results:
   1. [component] (unclear)
   2. [component] (unclear)
   3. [component] (unclear)
```

**This means:**
- ✅ Code works (didn't crash)
- ✅ Fallback protection works
- ❌ LLM normalization failed

**To debug:** Enable logging and re-run

## Output Files

Results saved to `output/validation_YYYYMMDD_HHMMSS.txt` with:
- Timestamp
- Pass/Fail status
- All findings
- Clear checklist

## Common Issues

### Issue: "API key: NOT SET"
**Fix:** `export ANTHROPIC_API_KEY='your-key'`

### Issue: "Module not found: deterministic_extractor"
**Status:** Should not happen - script uses correct import (`deterministic_wrapper`)

### Issue: All units show "(unclear)"
**Cause:** LLM call failed, fallback activated
**Debug:** Enable logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Issue: "Determinism: Types differ"
**Cause:** Cache not working or signature changed
**Check:** Look for warnings in output about cache invalidation

## Success Criteria

For production readiness, need:

- ✅ All 7 checkpoints pass
- ✅ 0 units in fallback mode
- ✅ 100% determinism (types match)
- ✅ Valid API key
- ✅ Candidates extracted (40+)

## Next Steps After Success

1. Scale test to 10, 20, 40 candidates
2. Measure actual API costs
3. Test on multiple videos
4. Deploy to production pipeline
