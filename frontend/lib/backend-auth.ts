// campaign-optimizer requires Cloud Run IAM auth (no unauthenticated ingress),
// so calls to it need an identity token minted for that exact audience via the
// metadata server - the same mechanism Cloud Scheduler uses to call it. Plus
// a separate, app-level shared secret (verify_internal_token in
// extended_server.py). Both are required; neither alone is sufficient.
async function fetchIdentityToken(audience: string): Promise<string | null> {
  try {
    const res = await fetch(
      `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(audience)}`,
      { headers: { "Metadata-Flavor": "Google" } }
    );
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

export function getBackendUrl(): string {
  return process.env.BACKEND_URL || "http://localhost:8000";
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
