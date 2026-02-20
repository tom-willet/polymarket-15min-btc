import { NextResponse } from "next/server";

const defaultBaseUrl =
  process.env.AGENT_API_BASE_URL ?? "http://127.0.0.1:8080";

export async function GET() {
  try {
    const res = await fetch(`${defaultBaseUrl}/reviews/latest`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
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
