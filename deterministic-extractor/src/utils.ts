
import { createHash } from "crypto";

/** Unicode-aware punctuation/symbol strip (with fallback). */
function stripPunctSymbols(s: string): string {
  try {
    // Node 20 supports Unicode property escapes
    return s.replace(/[\p{P}\p{S}]+/gu, " ");
  } catch {
    return s.replace(/[^\w\s]+/g, " ");
  }
}

export const canonText = (s: string) =>
  stripPunctSymbols(s)
    .normalize("NFKC")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();

export const words = (s: string) => {
  const t = canonText(s);
  return t.length ? t.split(" ").length : 0;
};

export const hash = (s: string) => createHash("sha256").update(s).digest("hex");
export const lex = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
export const cmpNum = (a: number, b: number) => (a < b ? -1 : a > b ? 1 : 0);
export const quant = (x: number) => Math.round(x * 1e6);

/** Deterministic 3-gram set */
export function ngrams3(s: string): Set<string> {
  const t = canonText(s);
  const out = new Set<string>();
  for (let i = 0; i < t.length - 2; i++) {
    out.add(t.slice(i, i + 3));
  }
  return out;
}

/** Jaccard similarity over 3-grams */
export function jaccard3(a: string, b: string): number {
  const A = ngrams3(a);
  const B = ngrams3(b);
  let inter = 0;
  for (const x of A) if (B.has(x)) inter++;
  const union = A.size + B.size - inter;
  return union ? inter / union : 1;
}

/** Windows by character length, snapping end to last '. ' in slice when possible. */
export function splitIntoWindowsByChars(
  s: string,
  windowChars: number
): { start: number; end: number; text: string; index: number }[] {
  const res: { start: number; end: number; text: string; index: number }[] = [];
  const len = s.length;
  let i = 0;
  let idx = 0;
  while (i < len) {
    let end = Math.min(i + windowChars, len);
    const boundary = s.slice(i, end).lastIndexOf(". ");
    if (boundary > 0 && end < len) end = i + boundary + 2;
    res.push({ start: i, end, text: s.slice(i, end), index: idx++ });
    i = end;
  }
  return res;
}

/** Deterministic sentence splitter (regex). */
export function sentenceSplit(
  s: string
): { text: string; start: number; end: number }[] {
  const out: { text: string; start: number; end: number }[] = [];
  const re = /[^.!?]+[.!?]+(?=(?:[\\"')\]]*\s+)|$)/g; // codepoint-based, deterministic
  let m: RegExpExecArray | null;
  while ((m = re.exec(s)) !== null) {
    const txt = m[0];
    const start = m.index;
    const end = m.index + txt.length;
    out.push({ text: txt, start, end });
  }
  if (out.length === 0 && s.trim()) {
    out.push({ text: s, start: 0, end: s.length });
  }
  return out;
}

export function imperativeBoost(s: string): 0 | 1 {
  const t = canonText(s);
  return /^(?:(?:you|we)\s+)?(?:must|should|never|always)\b|^(?:use|set|avoid|ensure|check|install|enable|disable|measure|calculate)\b/.test(
    t
  )
    ? 1
    : 0;
}

/** Canonical JSON (sorted keys) for stable hashing. */
export function canonicalSerialize(o: any): string {
  const seen = new WeakSet();
  const sortKeys = (v: any): any => {
    if (v && typeof v === "object") {
      if (seen.has(v)) return null;
      seen.add(v);
      if (Array.isArray(v)) return v.map(sortKeys);
      const keys = Object.keys(v).sort();
      const out: any = {};
      for (const k of keys) out[k] = sortKeys(v[k]);
      return out;
    }
    return v;
  };
  return JSON.stringify(sortKeys(o));
}
