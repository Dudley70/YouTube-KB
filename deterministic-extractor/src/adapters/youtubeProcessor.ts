
/**
 * Example adapter for a "youtube-processor" architecture.
 * You can call this from your pipeline where you have `videoId` and `transcript`.
 */

import { extractDeterministicUnits } from "../deterministicExtractor";
import { canonicalSerialize, hash } from "../utils";
import type { ExtractOptions } from "../types";

export type ExtractedUnitsEnvelope = {
  video_id: string;
  transcript_hash: string;
  units: ReturnType<typeof extractDeterministicUnits>["units"];
  meta?: ReturnType<typeof extractDeterministicUnits>["meta"];
};

export function processTranscriptDeterministic(
  video_id: string,
  transcript: string,
  opts: ExtractOptions = {}
): ExtractedUnitsEnvelope {
  const { units, meta } = extractDeterministicUnits(transcript, { ...opts, includeMeta: true });
  const payload = { video_id, units, meta };
  const transcript_hash = hash(canonicalSerialize({ video_id, transcript }));
  return { video_id, transcript_hash, units, meta };
}
