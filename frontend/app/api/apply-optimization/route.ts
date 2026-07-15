import { proxyToBackend } from "@/lib/backend-auth";

export async function POST() {
  return proxyToBackend("/api/apply-optimization", "POST", {});
}
