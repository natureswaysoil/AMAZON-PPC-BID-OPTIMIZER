import { proxyToBackend } from "@/lib/backend-auth";

export async function GET() {
  return proxyToBackend("/api/campaigns-debug", "GET");
}
