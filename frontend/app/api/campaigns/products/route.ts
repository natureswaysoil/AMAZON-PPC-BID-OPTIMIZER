import { NextRequest, NextResponse } from "next/server";

// campaign-optimizer requires Cloud Run IAM auth (no unauthenticated ingress),
// so calls to it need an identity token minted for that exact audience via the
// metadata server - the same mechanism Cloud Scheduler uses to call it.
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

export async function GET(req: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    const idToken = await fetchIdentityToken(backendUrl);
    const internalToken = process.env.DAILY_OPTIMIZER_TOKEN;

    // Call backend to get products preview. The identity token satisfies
    // Cloud Run's IAM ingress check; X-Daily-Optimizer-Token satisfies the
    // app's own verify_internal_token() - these are two separate auth layers.
    const response = await fetch(`${backendUrl}/api/campaign-products`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        ...(internalToken ? { "X-Daily-Optimizer-Token": internalToken } : {}),
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend error: ${response.statusText}` },
        { status: response.status }
      );
    }

    const products = await response.json();
    return NextResponse.json(products);
  } catch (error) {
    console.error("Error fetching products:", error);
    return NextResponse.json(
      { error: "Failed to fetch products" },
      { status: 500 }
    );
  }
}
