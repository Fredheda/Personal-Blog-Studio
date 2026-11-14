import { problemResponse } from "../../../../lib/problem";
import { proxy } from "../../../../lib/proxy";
import { getStudioToken } from "../../../../lib/token";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ path: string[] }> };

async function handle(request: Request, { params }: Context): Promise<Response> {
  const upstream = process.env.STUDIO_API_URL;
  if (!upstream) return problemResponse(503, "Service Unavailable");
  const { path } = await params;
  return proxy(request, path, { upstream, getToken: getStudioToken });
}

// No OPTIONS export: nothing here answers a cross-origin preflight.
export { handle as GET, handle as PUT, handle as PATCH, handle as POST, handle as DELETE };
