import { proxyToBackend } from "@/lib/backend-auth";

export async function POST(_req: Request, { params }: { params: { id: string } }) {
  return proxyToBackend(`/api/acos-circuit-breaker/clear/${encodeURIComponent(params.id)}`, "POST", {});
}
