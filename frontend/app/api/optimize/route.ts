export const dynamic = 'force-dynamic';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const { keywords } = await request.json();
  
  // This would call Cloud Run job to apply bid changes
  // For now, just log
  console.log('Applying bid changes to keywords:', keywords.length);
  
  return NextResponse.json({ success: true, updated: keywords.length });
}
