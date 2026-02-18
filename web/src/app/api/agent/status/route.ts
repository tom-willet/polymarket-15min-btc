import { NextResponse } from "next/server";

const defaultBaseUrl =
  process.env.AGENT_API_BASE_URL ?? "http://127.0.0.1:8080";

const ROUND_KEY_PATTERN = /(^|_)round(_|$)/i;

function stripRoundKeys(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => stripRoundKeys(item));
  }

  if (!value || typeof value !== "object") {
    return value;
  }

  const input = value as Record<string, unknown>;
  const output: Record<string, unknown> = {};

  for (const [key, child] of Object.entries(input)) {
    if (ROUND_KEY_PATTERN.test(key)) continue;
    output[key] = stripRoundKeys(child);
  }

  return output;
}

export async function GET() {
  try {
    const res = await fetch(`${defaultBaseUrl}/status`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(stripRoundKeys(data), { status: res.status });
  } catch (err) {
    return NextResponse.json(
      {
        error: "agent_api_unreachable",
        detail: err instanceof Error ? err.message : "unknown error",
      },
      { status: 502 },
    );
  }
}
