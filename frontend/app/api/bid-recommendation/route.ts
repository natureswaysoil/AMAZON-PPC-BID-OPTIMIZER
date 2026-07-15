import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-auth";

export async function GET(req: NextRequest) {
  const qs = req.nextUrl.search;
  return proxyToBackend(`/api/bid-recommendation${qs}`, "GET");
}
