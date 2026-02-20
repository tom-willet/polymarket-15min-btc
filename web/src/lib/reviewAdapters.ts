export type ReviewStatus = "queued" | "running" | "succeeded" | "failed";

export type ReviewSummary = {
  id: string;
  market_id: string;
  market_slug: string;
  round_close_ts: string;
  review_version: string;
  status: ReviewStatus;
  provider: string;
  model: string;
  created_at: string;
  updated_at: string;
};

export type ReviewDetail = ReviewSummary & {
  analysis_json?: Record<string, unknown> | null;
  analysis_markdown?: string | null;
  error_message?: string | null;
  latency_ms?: number | null;
  token_in?: number | null;
  token_out?: number | null;
  cost_usd_estimate?: number | null;
};

export type ReviewListPayload = {
  items: ReviewSummary[];
  next_cursor?: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

export function normalizeReviewSummary(value: unknown): ReviewSummary | null {
  if (!isRecord(value)) return null;
  const required = [
    "id",
    "market_id",
    "market_slug",
    "round_close_ts",
    "review_version",
    "status",
    "provider",
    "model",
    "created_at",
    "updated_at",
  ];
  for (const key of required) {
    if (typeof value[key] !== "string") return null;
  }
  return value as unknown as ReviewSummary;
}

export function normalizeReviewList(value: unknown): ReviewListPayload | null {
  if (!isRecord(value)) return null;
  if (!Array.isArray(value.items)) return null;

  const items = value.items
    .map((item) => normalizeReviewSummary(item))
    .filter((item): item is ReviewSummary => item !== null);

  return {
    items,
    next_cursor:
      typeof value.next_cursor === "string" ? value.next_cursor : null,
  };
}

export function normalizeReviewDetail(value: unknown): ReviewDetail | null {
  const summary = normalizeReviewSummary(value);
  if (!summary || !isRecord(value)) return null;

  return {
    ...summary,
    analysis_json: isRecord(value.analysis_json)
      ? (value.analysis_json as Record<string, unknown>)
      : null,
    analysis_markdown:
      typeof value.analysis_markdown === "string"
        ? value.analysis_markdown
        : null,
    error_message:
      typeof value.error_message === "string" ? value.error_message : null,
    latency_ms: typeof value.latency_ms === "number" ? value.latency_ms : null,
    token_in: typeof value.token_in === "number" ? value.token_in : null,
    token_out: typeof value.token_out === "number" ? value.token_out : null,
    cost_usd_estimate:
      typeof value.cost_usd_estimate === "number"
        ? value.cost_usd_estimate
        : null,
  };
}
