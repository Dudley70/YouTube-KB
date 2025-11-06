
# youtube-processor-deterministic

Deterministic extraction for YouTube transcripts. Implements **all 9 hardening fixes** we discussed:

1) **Tokenizer dependency** → windows by **character count**; all text normalized to **Unicode NFKC**.  
2) **Sentence splitter variability** → pinned deterministic regex splitter.  
3) **Sorting & collation** → **binary** (codepoint) lex compare (no `localeCompare`).  
4) **Float ties** → **quantized** scores before sorting.  
5) **Frequency definition** → lowercase, collapse whitespace, **strip punctuation & symbols**, **non-overlapping** matches.  
6) **Dedup threshold** → exact-normalize dedup, then optional **3‑gram Jaccard ≥ 0.92** near-dup collapse.  
7) **Window boundaries** → snap to previous sentence boundary inside each char window (deterministic).  
8) **Canonical JSON & hashing** → sorted-key serialization for stable SHA‑256.  
9) **LLM normalizer drift** → provided **cache interface** to freeze normalized fields `{video_id,id} → fields`.

## Quick start

```bash
pnpm i     # or: npm i
pnpm run build
pnpm test  # runs 20× hash determinism test

# print canonical hash + JSON for sample transcript
node dist/cli/hash-extractor.js fixtures/transcript.txt
```

## Key files

- `src/deterministicExtractor.ts` — extractor with all hardening fixes.
- `src/schema.ts` — strict JSON Schema for normalized outputs (Ajv).
- `src/utils.ts` — canonicalization, hashing, regex splitter, n-grams, stable comparators.
- `src/normalizerCache.ts` — simple file-backed cache interface for LLM output freezing.
- `src/adapters/youtubeProcessor.ts` — example wrapper to fit a typical YouTube pipeline.
- `test/determinism.test.ts` — 20-run hash validation using Vitest.
- `fixtures/transcript.txt` — sample transcript.
- `src/cli/hash-extractor.ts` — small CLI for local testing.
```

