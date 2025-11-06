
import fs from "fs";
import path from "path";
import { extractDeterministicUnits } from "../deterministicExtractor";
import { canonicalSerialize, hash } from "../utils";

const file = process.argv[2];
if (!file) {
  console.error("Usage: node dist/cli/hash-extractor.js <transcript.txt>");
  process.exit(1);
}

const abs = path.resolve(file);
const transcript = fs.readFileSync(abs, "utf8");
const { units, meta } = extractDeterministicUnits(transcript, { includeMeta: true });
const json = canonicalSerialize({ video_id: "cli", meta, units });
console.log("HASH:", hash(json));
console.log(json);
