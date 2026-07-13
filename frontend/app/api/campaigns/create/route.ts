import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { sku, daily_budget, starting_bid, dry_run } = await req.json();

    if (!sku) {
      return NextResponse.json(
        { error: "SKU is required" },
        { status: 400 }
      );
    }

    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

    // Call backend to create campaign
    const response = await fetch(`${backendUrl}/api/campaign-create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        sku,
        daily_budget: daily_budget || null,
        starting_bid: starting_bid || null,
        dry_run: dry_run !== false, // Default to dry run
      }),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend error: ${response.statusText}` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error("Error creating campaign:", error);
    return NextResponse.json(
      { error: "Failed to create campaign" },
      { status: 500 }
    );
  }
}
