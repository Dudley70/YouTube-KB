
import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { extractDeterministicUnits } from "../src/deterministicExtractor";
import { canonicalSerialize, hash } from "../src/utils";

describe("deterministic extractor (20-run hash)", () => {
  const transcript = fs.readFileSync(path.join(__dirname, "../fixtures/transcript.txt"), "utf8");

  it("produces identical hashes across 20 runs", () => {
    const hashes = new Set<string>();
    for (let i = 0; i < 20; i++) {
      const { units, meta } = extractDeterministicUnits(transcript, { includeMeta: true });
      const json = canonicalSerialize({ video_id: "dummy", meta, units });
      hashes.add(hash(json));
    }
    expect(hashes.size).toBe(1);
  });
});
