"""
Deterministic knowledge unit extraction from transcripts.

Ports the TypeScript deterministic extractor to pure Python, maintaining
100% identical output through careful implementation of:
- Exact text normalization (NFKC, lowercase, punctuation stripping)
- Deterministic sentence splitting (regex-based)
- Stable scoring and ranking with quantized comparisons
- Non-overlapping frequency counting
- Jaccard-based near-duplicate detection

Key principle: Same input → Same output, always.
"""

import re
import string
import unicodedata
from dataclasses import dataclass, asdict
from typing import List, Set, Optional, Dict, Any, Tuple


@dataclass
class Unit:
    """Knowledge unit candidate."""
    id: str
    text: str
    start: int
    end: int
    score: float
    window: int


@dataclass
class ExtractOptions:
    """Extraction configuration options."""
    window_chars: int = 3500
    target_count: Optional[int] = None
    min_words: int = 4
    max_words: int = 24
    jaccard_threshold: float = 0.92
    per_window_quota: Optional[int] = None
    include_meta: bool = False


@dataclass
class ExtractResult:
    """Extraction result with optional metadata."""
    units: List[Unit]
    meta: Optional[Dict[str, Any]] = None


# ============================================================================
# Text Normalization Utilities
# ============================================================================

def strip_punct_symbols(s: str) -> str:
    """
    Strip punctuation and symbols using unicodedata.
    
    Removes all characters in categories:
    - Punctuation (P*)
    - Symbols (S*)
    """
    result = []
    for char in s:
        cat = unicodedata.category(char)
        # Skip punctuation (P*) and symbols (S*)
        if not (cat.startswith('P') or cat.startswith('S')):
            result.append(char)
        else:
            result.append(' ')  # Replace with space
    return ''.join(result)


def canon_text(s: str) -> str:
    """
    Canonical text normalization for deterministic comparison.
    
    Steps:
    1. Strip punctuation/symbols
    2. NFKC normalization
    3. Lowercase
    4. Collapse whitespace
    5. Trim
    """
    # Strip punctuation and symbols
    s = strip_punct_symbols(s)
    # NFKC normalization
    s = unicodedata.normalize('NFKC', s)
    # Lowercase
    s = s.lower()
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s)
    # Trim
    return s.strip()


def words(s: str) -> int:
    """Count words in text after normalization."""
    t = canon_text(s)
    return len(t.split()) if t else 0

def quant(x: float) -> int:
    """Quantize float to integer for deterministic comparison (6 decimal places)."""
    return round(x * 1_000_000)


def lex(a: str, b: str) -> int:
    """Lexicographic comparison (-1, 0, 1)."""
    if a < b:
        return -1
    elif a > b:
        return 1
    else:
        return 0


# ============================================================================
# N-gram and Similarity
# ============================================================================

def ngrams3(s: str) -> Set[str]:
    """Generate deterministic 3-gram set from normalized text."""
    t = canon_text(s)
    out = set()
    for i in range(len(t) - 2):
        out.add(t[i:i+3])
    return out


def jaccard3(a: str, b: str) -> float:
    """Jaccard similarity over 3-grams."""
    A = ngrams3(a)
    B = ngrams3(b)
    inter = len(A & B)
    union = len(A) + len(B) - inter
    return inter / union if union > 0 else 1.0


# ============================================================================
# Text Segmentation
# ============================================================================

def split_into_windows_by_chars(
    s: str, 
    window_chars: int
) -> List[Dict[str, Any]]:
    """
    Split text into windows by character length, snapping to sentence boundaries.
    
    Tries to end windows at '. ' boundaries when possible, otherwise hard cuts.
    """
    result = []
    length = len(s)
    i = 0
    idx = 0
    
    while i < length:
        end = min(i + window_chars, length)
        
        # Try to snap to sentence boundary if not at end
        if end < length:
            boundary = s[i:end].rfind('. ')
            if boundary > 0:
                end = i + boundary + 2  # Include '. '
        
        result.append({
            'start': i,
            'end': end,
            'text': s[i:end],
            'index': idx
        })
        idx += 1
        i = end
    
    return result


def sentence_split(s: str) -> List[Dict[str, Any]]:
    """
    Deterministic sentence splitter using regex.
    
    Pattern matches: [text][.!?]+ followed by whitespace or end of string
    """
    out = []
    # Match sentences ending with punctuation
    pattern = r'[^.!?]+[.!?]+(?=(?:[\\"\')\]]*\s+)|$)'
    
    for match in re.finditer(pattern, s):
        txt = match.group(0)
        start = match.start()
        end = match.end()
        out.append({'text': txt, 'start': start, 'end': end})
    
    # Fallback: if no sentences found but text exists, treat as single sentence
    if not out and s.strip():
        out.append({'text': s, 'start': 0, 'end': len(s)})
    
    return out


def imperative_boost(s: str) -> int:
    """
    Detect imperative sentences for scoring boost.
    
    Returns 1 if imperative pattern detected, 0 otherwise.
    """
    t = canon_text(s)
    pattern = (
        r'^(?:(?:you|we)\s+)?(?:must|should|never|always)\b|'
        r'^(?:use|set|avoid|ensure|check|install|enable|disable|measure|calculate)\b'
    )
    return 1 if re.search(pattern, t) else 0


# ============================================================================
# Frequency Counting
# ============================================================================

def occurrences(haystack: str, needle: str) -> int:
    """
    Count non-overlapping occurrences of needle in haystack.
    
    Both inputs should already be canon_text() normalized.
    Returns 1 + count for weighting.
    """
    if not needle:
        return 0
    
    count = 0
    i = 0
    while True:
        i = haystack.find(needle, i)
        if i == -1:
            break
        count += 1
        i += len(needle)  # Non-overlapping
    
    return 1 + count  # 1 + frequency


# ============================================================================
# Helper Functions
# ============================================================================

def clamp(n: float, lo: float, hi: float) -> float:
    """Clamp number between min and max."""
    return max(lo, min(hi, n))


# ============================================================================
# Main Extraction Function
# ============================================================================

def extract_deterministic_units(
    transcript: str,
    opts: Optional[ExtractOptions] = None
) -> ExtractResult:
    """
    Extract deterministic knowledge units from transcript.
    
    Algorithm:
    1. Split transcript into windows (~3500 chars)
    2. Extract sentence candidates from each window
    3. Score based on: frequency (40%), early position (20%), 
       length normalized (20%), imperative boost (20%)
    4. Deduplicate exact matches (keep earliest)
    5. Collapse near-duplicates via Jaccard similarity
    6. Rank with deterministic tiebreakers
    7. Select top N candidates (40-90 based on length)
    
    Args:
        transcript: Full video transcript text
        opts: Extraction options (uses defaults if None)
    
    Returns:
        ExtractResult with selected units and optional metadata
    """
    if opts is None:
        opts = ExtractOptions()
    
    window_chars = opts.window_chars
    min_words = opts.min_words
    max_words = opts.max_words
    jaccard_threshold = opts.jaccard_threshold
    per_window_quota = opts.per_window_quota
    
    total_len = len(transcript)
    windows = split_into_windows_by_chars(transcript, window_chars)
    candidates: List[Unit] = []
    
    # Precompute normalized transcript for frequency
    transcript_norm = canon_text(transcript)
    
    # Process each window
    for w in windows:
        sentences = sentence_split(w['text'])
        window_cands: List[Unit] = []
        
        for s in sentences:
            abs_start = w['start'] + s['start']
            abs_end = w['start'] + s['end']
            text = transcript[abs_start:abs_end].strip()
            
            wcount = words(text)
            if wcount < min_words or wcount > max_words:
                continue
            
            norm = canon_text(text)
            occ = occurrences(transcript_norm, norm)
            
            # Scoring components
            early = 1 - (abs_start / total_len)
            imperative = imperative_boost(text)
            len_norm = min(wcount, max_words) / max_words
            
            # Combined score (40% frequency, 20% early, 20% length, 20% imperative)
            score = 0.4 * occ + 0.2 * early + 0.2 * len_norm + 0.2 * imperative
            
            unit_id = f"{w['index']}:{abs_start}-{abs_end}"
            window_cands.append(Unit(
                id=unit_id,
                text=text,
                start=abs_start,
                end=abs_end,
                score=score,
                window=w['index']
            ))
        
        # Optional per-window quota
        if per_window_quota and len(window_cands) > per_window_quota:
            # Sort with deterministic tiebreakers
            window_cands.sort(
                key=lambda u: (
                    -quant(u.score),  # Quantized score desc
                    u.start,          # Start asc
                    u.text           # Lex asc
                )
            )
            candidates.extend(window_cands[:per_window_quota])
        else:
            candidates.extend(window_cands)
    
    # Exact-normalized deduplication (keep earliest start)
    by_key: Dict[str, Unit] = {}
    for c in candidates:
        key = canon_text(c.text)
        prev = by_key.get(key)
        if prev is None or c.start < prev.start:
            by_key[key] = c
    
    deduped = list(by_key.values())
    
    # Sort by start for near-duplicate detection
    deduped.sort(key=lambda u: (u.start, u.text))
    
    # Near-duplicate collapse via Jaccard similarity
    collapsed: List[Unit] = []
    for u in deduped:
        if collapsed:
            last = collapsed[-1]
            if jaccard3(u.text, last.text) >= jaccard_threshold:
                # Skip near-duplicate (keep earliest)
                continue
        collapsed.append(u)
    
    # Global ranking with stable deterministic tiebreakers
    collapsed.sort(
        key=lambda u: (
            -quant(u.score),  # Quantized score desc
            u.window,         # Window asc
            u.start,          # Start asc
            u.text           # Lex asc
        )
    )
    
    # Determine target count (40-90 based on transcript length)
    if opts.target_count is not None:
        target_count = opts.target_count
    else:
        target_count = int(clamp(round(total_len / 2500), 40, 90))
    
    # Select top candidates
    selected = collapsed[:target_count]
    
    # Sort selected by start position for output
    selected.sort(key=lambda u: (u.start, u.text))
    
    # Build metadata if requested
    meta = None
    if opts.include_meta:
        import sys
        meta = {
            'extractor_version': '0.2.0-py',
            'window_chars': window_chars,
            'min_words': min_words,
            'max_words': max_words,
            'jaccard_threshold': jaccard_threshold,
            'per_window_quota': per_window_quota,
            'python_version': sys.version.split()[0]
        }
    
    return ExtractResult(units=selected, meta=meta)


# ============================================================================
# Convenience Functions
# ============================================================================

def extract_to_dict(
    transcript: str,
    opts: Optional[ExtractOptions] = None
) -> Dict[str, Any]:
    """
    Extract units and return as dictionary (for compatibility).
    
    Returns:
        {
            'units': [{'id': ..., 'text': ..., 'start': ..., 'end': ..., 'score': ..., 'window': ...}],
            'meta': {...} (optional)
        }
    """
    result = extract_deterministic_units(transcript, opts)
    return {
        'units': [asdict(u) for u in result.units],
        'meta': result.meta
    }
