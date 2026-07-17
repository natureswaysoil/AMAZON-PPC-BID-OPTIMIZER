import { NextRequest } from "next/server";
import { getPreviewServiceUrl, proxyToUrl } from "@/lib/backend-auth";

/** Proxies to backend/preview_server.py - a separate deployable from
 * campaign-optimizer (see lib/backend-auth.ts's getPreviewServiceUrl). */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return proxyToUrl(getPreviewServiceUrl(), "/preview", "POST", body);
}
