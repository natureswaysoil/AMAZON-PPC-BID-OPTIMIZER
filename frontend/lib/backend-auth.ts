import { GoogleAuth } from "google-auth-library";

// campaign-optimizer requires Cloud Run IAM auth (no unauthenticated ingress),
// so calls to it need an identity token minted for that exact audience. Use
// Google's auth client instead of calling the metadata server directly: it
// handles Cloud Run's runtime credentials and token refresh semantics.
const googleAuth = new GoogleAuth();

async function fetchIdentityToken(audience: string): Promise<string | null> {
  try {
    const client = await googleAuth.getIdTokenClient(audience);
    const headers = await client.getRequestHeaders();
    const authorization =
      typeof (headers as { get?: unknown }).get === "function"
        ? (headers as unknown as { get(name: string): string | null }).get("authorization")
        : (headers as unknown as Record<string, string>).Authorization ||
          (headers as unknown as Record<string, string>).authorization;
    return authorization?.replace(/^Bearer\s+/i, "") || null;
  } catch (error) {
    console.error("Unable to mint backend Cloud Run identity token:", error);
    return null;
  }
}

export function getBackendUrl(): string {
  return process.env.BACKEND_URL || "http://localhost:8000";
}

/** The bid-optimizer preview service (backend/preview_server.py) is a
 * separate Cloud Run deployable from campaign-optimizer, so it gets its own
 * base URL rather than reusing BACKEND_URL. */
export function getPreviewServiceUrl(): string {
  return process.env.PREVIEW_SERVICE_URL || "http://localhost:8080";
}

/** Headers needed to call campaign-optimizer directly (not through a browser,
 * which never sees these - this only runs in the Next.js server/route
 * handler). Always includes Content-Type; adds the two auth layers when
 * available so a local dev server without metadata/secrets still degrades
 * gracefully instead of throwing. */
export async function backendHeaders(backendUrl: string): Promise<Record<string, string>> {
  const idToken = await fetchIdentityToken(backendUrl);
  const internalToken = process.env.DAILY_OPTIMIZER_TOKEN;
  return {
    "Content-Type": "application/json",
    ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
    ...(internalToken ? { "X-Daily-Optimizer-Token": internalToken } : {}),
  };
}

import { NextResponse } from "next/server";

/** Same as proxyToBackend, but against an arbitrary base URL - used for the
 * preview service and any other deployable that isn't campaign-optimizer. */
export async function proxyToUrl(
  baseUrl: string,
  path: string,
  method: "GET" | "POST" | "PUT",
  body?: unknown
): Promise<NextResponse> {
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method,
      headers: await backendHeaders(baseUrl),
      ...(method !== "GET" ? { body: JSON.stringify(body ?? {}) } : {}),
      cache: "no-store",
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json(
        { error: data.message || `Backend error: ${response.statusText}` },
        { status: response.status }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error(`Error proxying ${method} ${path}:`, error);
    return NextResponse.json({ error: "Backend request failed" }, { status: 500 });
  }
}

/** Thin passthrough for the many action endpoints that take no meaningful
 * request body transformation (just forward whatever JSON body was sent,
 * or {} for GET). Used by simple one-shot action routes like
 * refresh-dashboard-cache, apply-negatives, retune-existing-bids, etc. */
export async function proxyToBackend(
  backendPath: string,
  method: "GET" | "POST" | "PUT",
  body?: unknown
): Promise<NextResponse> {
  return proxyToUrl(getBackendUrl(), backendPath, method, body);
}
