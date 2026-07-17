import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-auth";

/** Always forces confirm:true - only call this after the user has reviewed
 * the /api/campaign-templates/preview result and explicitly confirmed. */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return proxyToBackend("/api/launch-optimized", "POST", { ...body, confirm: true });
}
