import { proxyToBackend } from "@/lib/backend-auth";

export async function GET() {
  return proxyToBackend("/api/stacking-rules/types", "GET");
}
