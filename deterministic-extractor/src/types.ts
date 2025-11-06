export type Unit = {
  id: string;
  text: string;
  start: number;
  end: number;
  score: number;
  window: number;
};

export type ExtractOptions = {
  windowChars?: number; // default 3500
  targetCount?: number; // default based on transcript size
  minWords?: number;    // default 4
  maxWords?: number;    // default 24
  jaccardThreshold?: number; // default 0.92
  perWindowQuota?: number | null; // default null (no quota)
  includeMeta?: boolean; // include meta in JSON/hash if true
};

export type ExtractResult = {
  meta?: {
    extractorVersion: string;
    windowChars: number;
    minWords: number;
    maxWords: number;
    jaccardThreshold: number;
    perWindowQuota: number | null;
    nodeVersion: string;
  };
  units: Unit[];
};

export type NormalizedUnit = {
  id: string;
  canonical_title: string;
  category: "definition" | "tip" | "step" | "warning" | "claim" | "fact" | "example" | "misc";
  summary: string;
  confidence: number;
};

export type NormalizedOutput = {
  video_id: string;
  units: NormalizedUnit[];
};
