import { z } from "zod";

const nullableString = z.string().nullable().optional();
const synthesisStatusSchema = z.enum(["provisional", "final", "failed"]);

const verificationStatusSchema = z.enum(["verified", "unverified", "failed", "unavailable"]).optional();
const pipelineTypeSchema = z.enum(["structured", "legacy"]).optional();

const synthesisSnapshotFields = {
  contract_version: z.literal(1).optional(),
  debate_id: z.string().optional(),
  synthesis_id: z.string().min(1),
  run_attempt: z.number().int().nonnegative(),
  revision: z.number().int().nonnegative(),
  input_hash: z.string().optional(),
  response_ids: z.array(z.string()).default([]),
  successful_count: z.number().int().nonnegative(),
  total_count: z.number().int().nonnegative(),
  verification_status: verificationStatusSchema,
  is_verified: z.boolean().optional(),
  pipeline_type: pipelineTypeSchema,
  report_version: z.number().int().positive().optional(),
};

export const arenaSynthesisStartedSchema = z.object({
  type: z.literal("arena_synthesis_started"),
  ...synthesisSnapshotFields,
  status: z.enum(["provisional", "final"]),
}).passthrough();

export const arenaSynthesisRevisionSchema = z.object({
  type: z.literal("arena_synthesis_revision"),
  ...synthesisSnapshotFields,
  status: synthesisStatusSchema,
  content: z.string(),
  report: z.unknown().nullable().optional(),
}).passthrough();

export const arenaSynthesisFinalizedSchema = z.object({
  type: z.literal("arena_synthesis_finalized"),
  ...synthesisSnapshotFields,
  status: z.enum(["final", "failed"]),
  content: z.string(),
  report: z.unknown().nullable().optional(),
  provisional_promoted: z.boolean().optional(),
}).passthrough();

// Backward-compatible terminal event. New publishers include the versioned
// fields; old deployments may only provide content/meta.
export const legacyArenaSynthesisSchema = z.object({
  type: z.literal("arena_synthesis"),
  contract_version: z.literal(1).optional(),
  debate_id: z.string().optional(),
  synthesis_id: z.string().optional(),
  run_attempt: z.number().int().nonnegative().optional(),
  revision: z.number().int().nonnegative().optional(),
  status: synthesisStatusSchema.optional(),
  content: z.string().optional(),
  text: z.string().optional(),
  report: z.unknown().nullable().optional(),
  input_hash: z.string().optional(),
  response_ids: z.array(z.string()).optional(),
  successful_count: z.number().int().nonnegative().optional(),
  total_count: z.number().int().nonnegative().optional(),
  provisional_promoted: z.boolean().optional(),
  verification_status: verificationStatusSchema,
  is_verified: z.boolean().optional(),
  pipeline_type: pipelineTypeSchema,
  report_version: z.number().int().positive().optional(),
}).passthrough();

export const modelResponseDeltaSchema = z.object({
  type: z.literal("model_response_delta"),
  response_id: z.string().min(1),
  model_id: z.string().default(""),
  display_name: z.string().optional(),
  provider: z.string().optional(),
  text: z.string(),
  delta_sequence: z.number().int().nonnegative(),
  accumulated_chars: z.number().int().nonnegative().optional(),
  run_attempt: z.number().int().nonnegative().optional(),
  retry_generation: z.number().int().nonnegative().optional(),
}).passthrough();

export const synthesisDeltaSchema = z.object({
  type: z.literal("arena_synthesis_delta").optional(),
  synthesis_id: z.string().min(1).optional(),
  response_id: z.string().min(1).optional(),
  run_attempt: z.number().int().nonnegative(),
  revision: z.number().int().nonnegative(),
  status: z.enum(["provisional", "final"]),
  text: z.string(),
  delta_sequence: z.number().int().nonnegative(),
  input_hash: z.string().optional(),
  response_ids: z.array(z.string()).optional(),
  successful_count: z.number().int().nonnegative().optional(),
  total_count: z.number().int().nonnegative().optional(),
}).refine(
  value => Boolean(value.synthesis_id || value.response_id),
  { message: "synthesis_id or response_id is required" },
);

export const modelLifecycleSchema = z.object({
  type: z.enum([
    "model_response_queued",
    "model_response_connecting",
    "model_response_started",
    "model_response_persisting",
    "model_response_completed",
    "model_response_failed",
  ]),
  contract_version: z.literal(1).optional(),
  response_id: z.string().min(1),
  model_id: z.string().optional().default(""),
  display_name: z.string().optional(),
  provider: z.string().optional(),
  run_attempt: z.number().int().nonnegative().optional(),
  retry_generation: z.number().int().nonnegative().optional(),
  error: z.string().optional(),
  error_code: z.string().optional(),
}).passthrough();

export const arenaStartedSchema = z.object({
  type: z.literal("arena_started"),
  contract_version: z.literal(1).optional(),
  debate_id: z.string().optional(),
  models: z.array(z.object({
    model_id: z.string().min(1),
    display_name: z.string(),
    provider: z.string(),
    logo_url: nullableString,
    persona_type: nullableString,
    persona_tagline: nullableString,
  }).passthrough()),
}).passthrough();

export const arenaBoundaryEventSchema = z.discriminatedUnion("type", [
  arenaSynthesisStartedSchema,
  arenaSynthesisRevisionSchema,
  arenaSynthesisFinalizedSchema,
  legacyArenaSynthesisSchema,
  modelLifecycleSchema,
  arenaStartedSchema,
]);

const persistedResponseSchema = z.object({
  id: z.string(),
  response_id: z.string().optional(),
  debate_id: z.string(),
  response_type: z.string(),
  role: z.string(),
  round: z.number(),
  model_id: z.string(),
  display_name: z.string(),
  provider: z.string(),
  content: z.string(),
  success: z.boolean(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  retryable: z.boolean(),
  created_at: z.string().nullable(),
  metadata: z.object({
    logo_url: nullableString,
    persona_type: nullableString,
    persona_tagline: nullableString,
    attempt_count: z.number().int().nonnegative().optional(),
    run_attempt: z.number().int().nonnegative().optional(),
    retry_generation: z.number().int().nonnegative().optional(),
  }).passthrough(),
}).passthrough();

export const persistedResponsesSchema = z.object({
  contract_version: z.literal(1).optional(),
  items: z.array(persistedResponseSchema),
  summary: z.object({
    expected: z.number().int().nonnegative(),
    persisted: z.number().int().nonnegative(),
    successful: z.number().int().nonnegative(),
    failed: z.number().int().nonnegative(),
  }),
}).passthrough();

export type ArenaBoundaryEvent = z.infer<typeof arenaBoundaryEventSchema>;
export type ArenaSynthesisStartedEvent = z.infer<typeof arenaSynthesisStartedSchema>;
export type ArenaSynthesisRevisionEvent = z.infer<typeof arenaSynthesisRevisionSchema>;
export type ArenaSynthesisFinalizedEvent = z.infer<typeof arenaSynthesisFinalizedSchema>;

function flattenEnvelope(raw: unknown): unknown {
  if (!raw || typeof raw !== "object") return raw;
  const envelope = raw as Record<string, unknown>;
  const payload = envelope.payload;
  if (!payload || typeof payload !== "object") return envelope;
  const merged = {
    ...envelope,
    ...(payload as Record<string, unknown>),
  };
  const nestedPayload = merged.payload;
  if (!nestedPayload || typeof nestedPayload !== "object") return merged;
  return {
    ...merged,
    ...(nestedPayload as Record<string, unknown>),
  };
}

export function parseArenaBoundaryEvent(raw: unknown) {
  return arenaBoundaryEventSchema.safeParse(flattenEnvelope(raw));
}

export function parseModelResponseDelta(raw: unknown) {
  return modelResponseDeltaSchema.safeParse(flattenEnvelope(raw));
}

export function parseSynthesisDelta(raw: unknown) {
  return synthesisDeltaSchema.safeParse(flattenEnvelope(raw));
}

export function formatArenaSchemaDiagnostic(error: z.ZodError): string {
  return error.issues
    .slice(0, 4)
    .map((issue) => `${issue.path.join(".") || "event"}: ${issue.message}`)
    .join("; ");
}
