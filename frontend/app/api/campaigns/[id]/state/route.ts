import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-auth";

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  const body = await req.json().catch(() => ({}));
  return proxyToBackend(`/api/campaigns/${encodeURIComponent(params.id)}/state`, "PUT", body);
}
