# Phase A Live Test - CORRECTED

## Simple Test (RECOMMENDED)

**File:** `simple_test.py` - 137 lines, actually works

### What It Does

1. Gets a transcript from YouTube
2. Runs deterministic extraction (Step 1)
3. Runs Phase A LLM normalization on first 5 candidates (Step 2)
4. Shows results and detects if fallback mode was used

### Prerequisites

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### Run the Test

```bash
cd "/Users/dudley/Projects/YouTube Extractions/youtube-processor"
python3 tests/phase_a_live_test/simple_test.py
```

### Expected Output (SUCCESS)

```
================================================================================
SIMPLE PHASE A TEST
================================================================================

Testing with video: aA9KP7QIQvM

Step 1: Extracting transcript...
✅ Got 7,153 words

Step 2: Running deterministic extraction...
✅ Extracted 40 candidates
   Sample: The real question is, what types of work can Haiku...

Step 3: Running Phase A LLM normalization...
   (This will take 30-60 seconds...)
   Testing with 5 candidates
✅ Got 5 knowledge units

Results:
1. [technique] Haiku Performance Analysis
2. [pattern] Multi-Agent Observability
3. [concept] Speed vs Accuracy Tradeoff
4. [method] Tool Call Optimization
5. [observation] Prompt Engineering Impact

✅ SUCCESS - All units properly categorized!

================================================================================
TEST COMPLETE
================================================================================
```

### Expected Output (FALLBACK MODE)

If you see this:

```
Results:
1. [component] (unclear)
   ⚠️  FALLBACK MODE - LLM call failed
2. [component] (unclear)
   ⚠️  FALLBACK MODE - LLM call failed
...

❌ ALL UNITS IN FALLBACK MODE
   This means the LLM normalization failed.
   Possible causes:
   - Invalid API key
   - Rate limit hit  
   - Network timeout
   - LLM returned invalid JSON
```

**This means:**
- ✅ The code works (didn't crash)
- ✅ Fallback protection works
- ❌ LLM normalization failed for some reason

**To debug:**
1. Check your API key is valid
2. Check you're not hitting rate limits
3. Enable logging (see below)

### Debugging

Add logging to see what's actually failing:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Then run your code
```

This will show exactly what error the LLM normalizer encountered.

---

## Complex Test (NOT RECOMMENDED)

**File:** `test_latest_indydevdan.py` - 232 lines, has issues

This test has several problems:
- Uses wrong import paths
- Has API mismatches
- Tries to do too much at once
- Hardcodes video instead of fetching latest

**Use `simple_test.py` instead.**

---

## How It Works

### The Two-Step Pipeline

Phase A is **Step 2** in a two-step process:

```
Step 1: DeterministicExtractor
  Input:  Raw transcript (string)
  Output: 40-100 candidates with IDs
  Cost:   $0 (algorithmic)
  Time:   Fast (< 1 second)

Step 2: LLMNormalizer (Phase A)
  Input:  Candidates from Step 1
  Output: Categorized knowledge units
  Cost:   $0.09/video (with cache)
  Time:   30-60 seconds (first run)
```

### Why Two Steps?

**Cost savings:** 81% cheaper than sending full transcript to LLM

- Old way: $0.47/video (full transcript)
- New way: $0.09/video (just candidates)

**Design:** Decision #21 in PROJECT.md

### The Correct API

```python
# Step 1: Deterministic extraction
from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor

det = DeterministicExtractor()
result = det.extract(
    video_id="abc123",
    transcript="full transcript text here"
)
candidates = result['units']  # List of dicts

# Step 2: LLM normalization
from youtube_processor.llm.transcript_analyzer import TranscriptAnalyzer

analyzer = TranscriptAnalyzer(api_key="your-key")
analysis = analyzer.analyze_units(
    candidates=candidates,
    video_id="abc123",
    video_title="My Video"
)
units = analysis.knowledge_units  # List of KnowledgeUnit objects
```

---

## Common Issues

### Issue: "ModuleNotFoundError: deterministic_extractor"

**Fix:** Use `deterministic_wrapper` instead:
```python
from youtube_processor.extractors.deterministic_wrapper import DeterministicExtractor
```

### Issue: All units show "(unclear)" with confidence 0.30

**Cause:** LLM normalization failed, fallback mode activated

**Fix:** 
1. Check API key is valid
2. Check rate limits
3. Enable logging to see actual error
4. Try with fewer candidates (5 instead of 40)

### Issue: "AttributeError: 'dict' object has no attribute 'candidates'"

**Cause:** Result is a dict, not an object

**Fix:**
```python
result = det.extract(video_id=id, transcript=text)
candidates = result['units']  # Correct
# NOT: result.candidates
```

---

## Success Criteria

✅ Test completes without crashing  
✅ Gets transcript (thousands of words)  
✅ Extracts 40+ candidates  
✅ Normalizes 5 candidates  
✅ Shows proper types (NOT all "component/(unclear)")  

If you see all "(unclear)", the LLM call failed but the system didn't crash (which is good - fallback works).

---

## Next Steps

After `simple_test.py` works:

1. Test with more candidates (10, 20, 40)
2. Test determinism (run twice, compare)
3. Measure actual cost
4. Deploy to production pipeline

For help, see: `docs/HOW_TO_USE_PHASE_A.md`
