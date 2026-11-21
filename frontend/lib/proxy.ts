import { problemResponse } from "./problem";

export const MAX_BODY_BYTES = 1_048_576;
// The studio API scales to zero and takes 28 to 30 s to start; 30 s lost the race by a second.
export const UPSTREAM_TIMEOUT_MS = 60_000;
export const WAKING_UP = "The studio API is waking up. Try again in a moment.";

/** One log value: printable ASCII only and short, so an upstream cannot forge lines. */
const clean = (value: string | null) => (value === null ? "-" : value.replace(/[^\x20-\x7e]/g, "?").slice(0, 120));

function logAnswer(method: string, segments: string[], status: number, headers: Headers, length: number) {
  console.log(
    `studio proxy: ${method} /${segments.join("/")} ${status} content-type=${clean(headers.get("content-type"))} length=${length} server=${clean(headers.get("server"))} www-authenticate=${clean(headers.get("www-authenticate"))}`,
  );
}

const METHODS = new Set(["GET", "PUT", "PATCH", "POST", "DELETE"]);
const SEGMENT = /^[A-Za-z0-9_-]{1,64}$/;
// Headers the browser may pass on. X-Blog-Studio and Origin are forwarded
// exactly as sent (the studio API's same-origin guard judges them); this proxy
// never adds either one.
const FORWARDED = ["content-type", "accept", "if-match", "x-blog-studio", "origin"];
const RETURNED = ["content-type", "etag"];

export type ProxyDeps = {
  upstream: string;
  getToken: () => Promise<string | null>;
  fetchImpl?: typeof fetch;
};

/** Read the request body, counting as it arrives: a chunked body stops being
 *  read the moment it passes `max` (the stream is cancelled). Returns null then. */
async function readCapped(request: Request, max: number): Promise<Uint8Array<ArrayBuffer> | null> {
  if (request.body === null) return new Uint8Array(0);
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > max) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out;
}

/** The one query the proxy passes on: `confirm=published` on DELETE /posts/{id}. */
function upstreamQuery(request: Request, segments: string[]): string {
  if (request.method !== "DELETE" || segments.length !== 2) return "";
  const confirm = new URL(request.url).searchParams.getAll("confirm");
  return confirm.length === 1 && confirm[0] === "published" ? "?confirm=published" : "";
}

export async function proxy(
  request: Request,
  segments: string[],
  deps: ProxyDeps,
): Promise<Response> {
  if (!METHODS.has(request.method)) {
    return problemResponse(405, "Method Not Allowed", { allow: [...METHODS].join(", ") });
  }
  if (segments[0] !== "posts" || !segments.every((s) => SEGMENT.test(s))) {
    return problemResponse(404, "Not Found");
  }
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_BODY_BYTES) {
    return problemResponse(413, "Content Too Large");
  }

  let body: Uint8Array<ArrayBuffer> | undefined;
  if (request.method !== "GET" && request.method !== "DELETE") {
    const read = await readCapped(request, MAX_BODY_BYTES);
    if (read === null) return problemResponse(413, "Content Too Large");
    if (read.byteLength > 0) body = read;
  }

  try {
    const headers = new Headers();
    for (const name of FORWARDED) {
      const value = request.headers.get(name);
      if (value !== null) headers.set(name, value);
    }
    const token = await deps.getToken();
    if (token !== null) headers.set("authorization", `Bearer ${token}`);
    const upstream = await (deps.fetchImpl ?? fetch)(
      `${deps.upstream.replace(/\/$/, "")}/${segments.join("/")}${upstreamQuery(request, segments)}`,
      {
        method: request.method,
        headers,
        body,
        // A redirect is never followed: it would carry the bearer token to
        // another host. Any 3xx is treated as a failure below.
        redirect: "manual",
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      },
    );
    if (upstream.status >= 300 && upstream.status < 400) {
      logAnswer(request.method, segments, upstream.status, upstream.headers, 0);
      console.error("studio proxy: the upstream answered a redirect");
      return problemResponse(502, "Bad Gateway");
    }
    const payload = upstream.status === 204 ? null : await upstream.arrayBuffer();
    logAnswer(request.method, segments, upstream.status, upstream.headers, payload?.byteLength ?? 0);
    const out = new Headers({ "cache-control": "no-store" });
    for (const name of RETURNED) {
      const value = upstream.headers.get(name);
      if (value !== null) out.set(name, value);
    }
    const location = upstream.headers.get("location");
    if (location?.startsWith("/posts/")) out.set("location", `/api/studio${location}`);
    return new Response(payload, { status: upstream.status, headers: out });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError") {
      console.error("studio proxy: the upstream did not answer in time");
      return problemResponse(504, "Gateway Timeout", { "retry-after": "5" }, WAKING_UP);
    }
    console.error("studio proxy failed:", error instanceof Error ? error.name : "unknown");
    return problemResponse(502, "Bad Gateway");
  }
}
