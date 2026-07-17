import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-auth";

export async function GET(req: NextRequest) {
  const scope = req.nextUrl.searchParams.get("scope") || "default";
  return proxyToBackend(`/api/stacking-rules?scope=${encodeURIComponent(scope)}`, "GET");
}

export async function PUT(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return proxyToBackend("/api/stacking-rules", "PUT", body);
}
