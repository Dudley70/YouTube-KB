
import fs from "fs";
import path from "path";

export type NormalizedCacheRecord = {
  canonical_title: string;
  category: string;
  summary: string;
  confidence: number;
};

export type NormalizedCache = Record<string, NormalizedCacheRecord>; // key: `${video_id}:${id}`

/**
 * File-backed normalized output cache to freeze LLM drift.
 * Deterministic: same transcript hash + IDs -> same normalized fields.
 */
export class NormalizerCache {
  private file: string;
  private data: NormalizedCache = {};

  constructor(filePath: string) {
    this.file = path.resolve(filePath);
    if (fs.existsSync(this.file)) {
      try {
        this.data = JSON.parse(fs.readFileSync(this.file, "utf8"));
      } catch {
        this.data = {};
      }
    }
  }

  key(video_id: string, id: string) {
    return `${video_id}:${id}`;
  }

  get(video_id: string, id: string): NormalizedCacheRecord | undefined {
    return this.data[this.key(video_id, id)];
  }

  set(video_id: string, id: string, rec: NormalizedCacheRecord) {
    this.data[this.key(video_id, id)] = rec;
  }

  save() {
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
    fs.writeFileSync(this.file, JSON.stringify(this.data, null, 2), "utf8");
  }
}
