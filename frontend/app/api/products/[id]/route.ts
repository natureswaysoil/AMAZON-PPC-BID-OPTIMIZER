import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl, backendHeaders } from "@/lib/backend-auth";

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const payload = await req.json();
    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/products/${encodeURIComponent(params.id)}`, {
      method: "PUT",
      headers: await backendHeaders(backendUrl),
      body: JSON.stringify(payload),
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
    console.error("Error updating product:", error);
    return NextResponse.json({ error: "Failed to update product" }, { status: 500 });
  }
}
