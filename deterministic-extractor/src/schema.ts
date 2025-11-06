
export const NormalizedSchema = {
  type: "object",
  properties: {
    video_id: { type: "string", minLength: 3 },
    units: {
      type: "array",
      items: {
        type: "object",
        properties: {
          id: { type: "string" },
          canonical_title: { type: "string", pattern: "^(\\S+)(\\s+\\S+){0,7}$" },
          category: {
            type: "string",
            enum: ["definition", "tip", "step", "warning", "claim", "fact", "example", "misc"],
          },
          summary: { type: "string", minLength: 1, maxLength: 300 },
          confidence: { type: "number", minimum: 0, maximum: 1 },
        },
        required: ["id", "canonical_title", "category", "summary", "confidence"],
        additionalProperties: false,
      },
    },
  },
  required: ["video_id", "units"],
  additionalProperties: false,
} as const;
