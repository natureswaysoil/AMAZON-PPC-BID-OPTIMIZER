import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-auth";

/** Always forces confirm:false regardless of what the client sends - this
 * route is the read-only preview step; use /api/campaign-templates/launch
 * to actually create campaigns. */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return proxyToBackend("/api/launch-optimized", "POST", { ...body, confirm: false });
}
