import { NextResponse } from "next/server";

const GAMMA_BASE_URL = "https://gamma-api.polymarket.com";
const WINDOW_SECONDS = 15 * 60;

function getCandidateSlugs(nowTs: number): string[] {
  const aligned = Math.floor(nowTs / WINDOW_SECONDS) * WINDOW_SECONDS;
  const candidates = [
    aligned,
    aligned - WINDOW_SECONDS,
    aligned - 2 * WINDOW_SECONDS,
    aligned + WINDOW_SECONDS,
  ];
  return candidates.map((ts) => `btc-updown-15m-${ts}`);
}

function collectTokenIds(value: unknown, output: Set<string>): void {
  if (value == null) return;

  if (typeof value === "string") {
    const trimmed = value.trim();

    if (/^\d{8,}$/.test(trimmed)) {
      output.add(trimmed);
      return;
    }

    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      try {
        const parsed = JSON.parse(trimmed) as unknown;
        collectTokenIds(parsed, output);
      } catch {
        return;
      }
    }

    return;
  }

  if (Array.isArray(value)) {
    for (const entry of value) collectTokenIds(entry, output);
    return;
  }

  if (typeof value === "object") {
    const record = value as Record<string, unknown>;

    for (const [key, entry] of Object.entries(record)) {
      const normalized = key.toLowerCase();
      if (
        normalized.includes("token") ||
        normalized.includes("asset") ||
        normalized === "clobtokenids" ||
        normalized === "clobtokenid"
      ) {
        collectTokenIds(entry, output);
      }

      if (typeof entry === "object" && entry !== null) {
        collectTokenIds(entry, output);
      }
    }
  }
}

async function lookupSlug(
  slug: string,
): Promise<{ slug: string; tokenIds: string[] } | null> {
  const response = await fetch(`${GAMMA_BASE_URL}/markets/slug/${slug}`, {
    cache: "no-store",
  });
  if (!response.ok) return null;

  const payload = (await response.json()) as unknown;
  const tokenSet = new Set<string>();
  collectTokenIds(payload, tokenSet);

  const tokenIds = [...tokenSet];
  if (tokenIds.length < 2) return null;

  return {
    slug,
    tokenIds: tokenIds.slice(0, 2),
  };
}

export async function GET() {
  try {
    const nowTs = Math.floor(Date.now() / 1000);
    const slugs = getCandidateSlugs(nowTs);

    for (const slug of slugs) {
      const market = await lookupSlug(slug);
      if (market) {
        return NextResponse.json({ ok: true, ...market });
      }
    }

    return NextResponse.json(
      {
        ok: false,
        error: "active_market_not_found",
        attemptedSlugs: slugs,
      },
      { status: 404 },
    );
  } catch (err) {
    return NextResponse.json(
      {
        ok: false,
        error: "gamma_lookup_failed",
        detail: err instanceof Error ? err.message : "unknown error",
      },
      { status: 502 },
    );
  }
}
