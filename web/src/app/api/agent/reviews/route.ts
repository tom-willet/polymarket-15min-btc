import { NextRequest, NextResponse } from "next/server";

const defaultBaseUrl =
  process.env.AGENT_API_BASE_URL ?? "http://127.0.0.1:8080";

export async function GET(request: NextRequest) {
  try {
    const limit = request.nextUrl.searchParams.get("limit") ?? "50";
    const status = request.nextUrl.searchParams.get("status");
    const params = new URLSearchParams({ limit });
    if (status) params.set("status", status);

    const res = await fetch(`${defaultBaseUrl}/reviews?${params.toString()}`, {
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
