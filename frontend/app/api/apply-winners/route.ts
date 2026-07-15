import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-auth";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return proxyToBackend("/api/apply-winners", "POST", body);
}
