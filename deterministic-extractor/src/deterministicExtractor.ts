
import { ExtractOptions, Unit, ExtractResult } from "./types";
import {
  canonText,
  words,
  splitIntoWindowsByChars,
  sentenceSplit,
  imperativeBoost,
  cmpNum,
  lex,
  quant,
  jaccard3,
} from "./utils";

/**
 * Deterministic extractor with 9 hardening fixes implemented.
 */
export function extractDeterministicUnits(
  transcript: string,
  opts: ExtractOptions = {}
): ExtractResult {
  const windowChars = opts.windowChars ?? 3500;
  const minWords = opts.minWords ?? 4;
  const maxWords = opts.maxWords ?? 24;
  const jaccardThreshold = opts.jaccardThreshold ?? 0.92;
  const perWindowQuota = opts.perWindowQuota ?? null;

  const totalLen = transcript.length;
  const windows = splitIntoWindowsByChars(transcript, windowChars);
  const candidates: Unit[] = [];

  // Precompute normalized transcript for frequency calculation
  const transcriptNorm = canonText(transcript);

  for (const w of windows) {
    const sentences = sentenceSplit(w.text);
    const windowCands: Unit[] = [];

    for (const s of sentences) {
      const absStart = w.start + s.start;
      const absEnd = w.start + s.end;
      const text = transcript.slice(absStart, absEnd).trim();

      const wcount = words(text);
      if (wcount < minWords || wcount > maxWords) continue;

      const norm = canonText(text);
      const occ = occurrences(transcriptNorm, norm); // deterministic, non-overlapping

      const early = 1 - absStart / totalLen;
      const imperative = imperativeBoost(text);
      const lenNorm = Math.min(wcount, maxWords) / maxWords;

      const score = 0.4 * occ + 0.2 * early + 0.2 * lenNorm + 0.2 * imperative;
      const id = `${w.index}:${absStart}-${absEnd}`;

      windowCands.push({
        id,
        text,
        start: absStart,
        end: absEnd,
        score,
        window: w.index,
      });
    }

    // Optional per-window quota before global selection (deterministic)
    if (perWindowQuota && windowCands.length > perWindowQuota) {
      windowCands.sort(
        (a, b) =>
          // quantized score desc
          (quant(b.score) - quant(a.score)) ||
          // start asc
          (a.start - b.start) ||
          // binary lex asc
          lex(a.text, b.text)
      );
      candidates.push(...windowCands.slice(0, perWindowQuota));
    } else {
      candidates.push(...windowCands);
    }
  }

  // Exact-normalized dedup (keep earliest start)
  const byKey = new Map<string, Unit>();
  for (const c of candidates) {
    const key = canonText(c.text);
    const prev = byKey.get(key);
    if (!prev || c.start < prev.start) byKey.set(key, c);
  }
  let deduped = Array.from(byKey.values());

  // Optional near-duplicate collapse via 3-gram Jaccard
  deduped.sort((a, b) => (a.start - b.start) || lex(a.text, b.text));
  const collapsed: Unit[] = [];
  for (const u of deduped) {
    const last = collapsed.length ? collapsed[collapsed.length - 1] : null;
    if (last && jaccard3(u.text, last.text) >= jaccardThreshold) {
      // keep the earliest (already ensured), skip u
      continue;
    }
    collapsed.push(u);
  }

  // Global ranking with stable, deterministic tiebreakers
  collapsed.sort(
    (a, b) =>
      (quant(b.score) - quant(a.score)) ||
      (a.window - b.window) ||
      (a.start - b.start) ||
      lex(a.text, b.text)
  );

  const targetCount = opts.targetCount ?? clamp(Math.round(totalLen / 2500), 40, 90);
  const selected = collapsed
    .slice(0, targetCount)
    .sort((a, b) => (a.start - b.start) || lex(a.text, b.text));

  const meta = {
    extractorVersion: "0.2.0",
    windowChars,
    minWords,
    maxWords,
    jaccardThreshold,
    perWindowQuota,
    nodeVersion: process.version,
  };

  return { meta: opts.includeMeta ? meta : undefined, units: selected };
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

/** Non-overlapping frequency of `needle` in `hay`, both already canonText()-ed. */
function occurrences(hay: string, needle: string): number {
  if (!needle) return 0;
  let count = 0;
  let i = 0;
  while ((i = hay.indexOf(needle, i)) !== -1) {
    count++;
    i += needle.length;
  }
  return 1 + count; // 1 + frequency as extra weighting
}

export default extractDeterministicUnits;
