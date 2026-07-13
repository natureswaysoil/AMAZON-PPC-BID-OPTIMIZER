import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { sku } = await req.json();

    if (!sku) {
      return NextResponse.json(
        { error: "SKU is required" },
        { status: 400 }
      );
    }

    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

    // Call backend to get campaign preview
    const response = await fetch(`${backendUrl}/api/campaign-preview`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ sku }),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend error: ${response.statusText}` },
        { status: response.status }
      );
    }

    const preview = await response.json();
    return NextResponse.json(preview);
  } catch (error) {
    console.error("Error fetching campaign preview:", error);
    return NextResponse.json(
      { error: "Failed to fetch campaign preview" },
      { status: 500 }
    );
  }
}
