import Ajv from "ajv";
import { NormalizedSchema } from "./schema";
import type { NormalizedOutput } from "./types";

const ajv = new Ajv({ allErrors: true, strict: true });
const validateFn = ajv.compile(NormalizedSchema);

export function validateNormalizedOutput(
  o: unknown
): { valid: boolean; errors?: string[] } {
  const valid = validateFn(o);
  if (valid) return { valid: true };
  return {
    valid: false,
    errors: (validateFn.errors || []).map((e) => `${e.instancePath} ${e.message}`),
  };
}
