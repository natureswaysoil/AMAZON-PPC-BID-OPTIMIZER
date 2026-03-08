export const dynamic = 'force-dynamic';
import { NextResponse } from 'next/server';

// Settings are stored in a simple JSON file or can use Firestore/Cloud Storage
export async function GET() {
  // Return current settings from config
  return NextResponse.json({
    target_acos: 0.30,
    min_bid: 0.30,
    max_bid: 5.00,
    peak_hours: [16, 17, 18, 19, 20, 21],
    peak_multiplier: 1.10,
    offpeak_multiplier: 0.90,
    enable_auto_bidding: true,
    aov_tiers: {
      L: { min: 18, max: 29, ceiling: 1.05 },
      M: { min: 30, max: 45, ceiling: 1.45 },
      H: { min: 46, max: 70, ceiling: 1.95 },
      X: { min: 70, max: 999, ceiling: 2.50 }
    }
  });
}

export async function POST(request: Request) {
  const settings = await request.json();
  // In production, save to Cloud Storage or Firestore
  console.log('Settings updated:', settings);
  return NextResponse.json({ success: true, settings });
}
