import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

async function findLogsRoot(): Promise<string | null> {
  const candidates = [
    path.resolve(process.cwd(), "logs"),
    path.resolve(process.cwd(), "..", "logs"),
  ];

  for (const candidate of candidates) {
    try {
      const stat = await fs.stat(candidate);
      if (stat.isDirectory()) {
        return candidate;
      }
    } catch {
      continue;
    }
  }

  return null;
}

export async function GET() {
  const logsRoot = await findLogsRoot();
  if (!logsRoot) {
    return NextResponse.json(
      {
        error: "continuous_run_not_found",
        detail: "logs directory not found",
      },
      { status: 404 },
    );
  }

  const pointerPath = path.join(logsRoot, "latest_continuous_run_path.txt");

  let runPath: string;
  try {
    runPath = (await fs.readFile(pointerPath, "utf-8")).trim();
  } catch {
    return NextResponse.json(
      {
        error: "continuous_run_not_found",
        detail: "latest run pointer is missing",
      },
      { status: 404 },
    );
  }

  const absoluteRunPath = path.isAbsolute(runPath)
    ? runPath
    : path.resolve(process.cwd(), "..", runPath);

  try {
    const raw = await fs.readFile(absoluteRunPath, "utf-8");
    const payload = JSON.parse(raw);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      {
        error: "continuous_run_unreadable",
        detail: error instanceof Error ? error.message : "unknown error",
      },
      { status: 502 },
    );
  }
}
