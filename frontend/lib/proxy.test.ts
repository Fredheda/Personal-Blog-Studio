// @vitest-environment node
import { afterEach, describe, expect, test, vi } from "vitest";

import { MAX_BODY_BYTES, proxy, UPSTREAM_TIMEOUT_MS, WAKING_UP } from "./proxy";

type Call = { url: string; init: RequestInit };

function setup(reply: () => Response | Promise<Response> = () => Response.json({ ok: true })) {
  const calls: Call[] = [];
  const fetchImpl = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init: init ?? {} });
    return reply();
  }) as unknown as typeof fetch;
  const deps = { upstream: "http://studio-api", getToken: async () => "tok", fetchImpl };
  return { calls, deps };
}

function req(method: string, path: string, init: RequestInit = {}) {
  return new Request(`https://studio.example${path}`, { method, ...init });
}

describe("allowlist", () => {
  test.each([
    ["GET", ["healthz"]],
    ["GET", ["posts", ".."]],
    ["GET", ["posts", "a%2Fb"]],
    ["GET", ["posts", "x".repeat(65)]],
    ["GET", []],
    ["OPTIONS", ["posts"]],
    ["HEAD", ["posts"]],
  ])("%s %j never reaches the upstream", async (method, segments) => {
    const { calls, deps } = setup();
    const response = await proxy(req(method, "/api/studio/x"), segments, deps);
    expect([404, 405]).toContain(response.status);
    expect(response.headers.get("content-type")).toContain("application/problem+json");
    expect(calls).toHaveLength(0);
  });

  test("no response carries a CORS header", async () => {
    const { deps } = setup();
    const ok = await proxy(req("GET", "/api/studio/posts"), ["posts"], deps);
    const refused = await proxy(req("OPTIONS", "/api/studio/posts"), ["posts"], deps);
    for (const r of [ok, refused]) {
      expect([...r.headers.keys()].some((k) => k.startsWith("access-control-"))).toBe(false);
    }
  });
});

describe("forwarding", () => {
  test.each([
    ["GET", ["posts", "ID", "check"], "http://studio-api/posts/ID/check"],
    ["DELETE", ["posts", "ID"], "http://studio-api/posts/ID"],
  ])("%s %j is forwarded", async (method, segments, url) => {
    const { calls, deps } = setup();
    await proxy(req(method, `/api/studio/${segments.join("/")}`), segments, deps);
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe(url);
    expect(calls[0].init.method).toBe(method);
  });

  test("adds the bearer token, keeps X-Blog-Studio and Origin as sent, drops the rest", async () => {
    const { calls, deps } = setup();
    await proxy(
      req("PUT", "/api/studio/posts/ID/body?x=1", {
        body: '{"body":"hi"}',
        headers: {
          "content-type": "application/json",
          "if-match": '"0x1"',
          "x-blog-studio": "1",
          origin: "https://studio.example",
          cookie: "AppServiceAuthSession=secret",
          authorization: "Bearer browser-supplied",
          "x-ms-client-principal": "abc",
        },
      }),
      ["posts", "ID", "body"],
      deps,
    );
    const { url, init } = calls[0];
    expect(url).toBe("http://studio-api/posts/ID/body");
    const sent = new Headers(init.headers);
    expect(sent.get("authorization")).toBe("Bearer tok");
    expect(sent.get("x-blog-studio")).toBe("1");
    expect(sent.get("origin")).toBe("https://studio.example");
    expect(sent.get("if-match")).toBe('"0x1"');
    expect(sent.get("content-type")).toBe("application/json");
    expect(sent.get("cookie")).toBeNull();
    expect(sent.get("x-ms-client-principal")).toBeNull();
  });

  test("never invents X-Blog-Studio or Origin", async () => {
    const { calls, deps } = setup();
    await proxy(req("POST", "/api/studio/posts"), ["posts"], deps);
    const sent = new Headers(calls[0].init.headers);
    expect(sent.get("x-blog-studio")).toBeNull();
    expect(sent.get("origin")).toBeNull();
  });

  test("relays status, body, etag and a rewritten location, always no-store", async () => {
    const { deps } = setup(
      () =>
        new Response('{"postId":"ID"}', {
          status: 201,
          headers: {
            "content-type": "application/json",
            etag: '"0x2"',
            location: "/posts/ID",
            "set-cookie": "x=1",
            server: "uvicorn",
          },
        }),
    );
    const response = await proxy(req("POST", "/api/studio/posts"), ["posts"], deps);
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ postId: "ID" });
    expect(response.headers.get("etag")).toBe('"0x2"');
    expect(response.headers.get("location")).toBe("/api/studio/posts/ID");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(response.headers.get("server")).toBeNull();
  });

  test("relays an upstream problem+json unchanged", async () => {
    const { deps } = setup(
      () =>
        new Response('{"status":412,"title":"Precondition Failed"}', {
          status: 412,
          headers: { "content-type": "application/problem+json" },
        }),
    );
    const response = await proxy(req("PUT", "/api/studio/posts/ID/body", { body: "{}" }), ["posts", "ID", "body"], deps);
    expect(response.status).toBe(412);
    expect(response.headers.get("content-type")).toContain("application/problem+json");
  });
});

describe("limits and failures", () => {
  test("a declared body over the cap is 413 without calling the upstream", async () => {
    const { calls, deps } = setup();
    const response = await proxy(
      req("PUT", "/api/studio/posts/ID/body", {
        body: "x",
        headers: { "content-length": String(MAX_BODY_BYTES + 1) },
      }),
      ["posts", "ID", "body"],
      deps,
    );
    expect(response.status).toBe(413);
    expect(calls).toHaveLength(0);
  });

  test("a real body over the cap is 413 even without a content-length", async () => {
    const { calls, deps } = setup();
    const big = new Uint8Array(MAX_BODY_BYTES + 1);
    const response = await proxy(req("PUT", "/api/studio/posts/ID/body", { body: big }), ["posts", "ID", "body"], deps);
    expect(response.status).toBe(413);
    expect(calls).toHaveLength(0);
  });

  test("a chunked body is cancelled as soon as it passes the cap", async () => {
    const { calls, deps } = setup();
    let pulled = 0;
    let cancelled = false;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        pulled += 1;
        controller.enqueue(new Uint8Array(256 * 1024));
      },
      cancel() {
        cancelled = true;
      },
    });
    const request = new Request("https://studio.example/api/studio/posts/ID/body", {
      method: "PUT",
      body: stream,
      // @ts-expect-error Node needs duplex for a streamed request body
      duplex: "half",
    });
    const response = await proxy(request, ["posts", "ID", "body"], deps);
    expect(response.status).toBe(413);
    expect(calls).toHaveLength(0);
    expect(cancelled).toBe(true);
    expect(pulled).toBeLessThan(10); // 1 MiB / 256 KiB = 4, plus queue read-ahead
  });

  test("a redirect from the upstream is never followed and is a fixed 502", async () => {
    const { calls, deps } = setup(
      () => new Response(null, { status: 307, headers: { location: "https://elsewhere.example/posts" } }),
    );
    const response = await proxy(req("GET", "/api/studio/posts"), ["posts"], deps);
    expect(response.status).toBe(502);
    expect(response.headers.get("location")).toBeNull();
    expect((calls[0].init as RequestInit).redirect).toBe("manual");
  });

  test("a failing upstream or token is a fixed 502 that leaks nothing", async () => {
    const failing = {
      upstream: "http://studio-api",
      getToken: async () => {
        throw new Error("secret detail https://acct.blob.core.windows.net");
      },
      fetchImpl: vi.fn() as unknown as typeof fetch,
    };
    const response = await proxy(req("GET", "/api/studio/posts"), ["posts"], failing);
    const text = await response.text();
    expect(response.status).toBe(502);
    expect(text).not.toContain("secret");
    expect(JSON.parse(text)).toMatchObject({ status: 502, title: "Bad Gateway" });
  });
});

describe("cold start and diagnostics", () => {
  afterEach(() => vi.restoreAllMocks());

  test("the upstream gets 60 seconds", () => {
    expect(UPSTREAM_TIMEOUT_MS).toBe(60_000);
  });

  test("a timeout is a 504 problem+json that says the studio API is waking up", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const timeout = Object.assign(new Error("timed out"), { name: "TimeoutError" });
    const { deps } = setup(() => {
      throw timeout;
    });
    const response = await proxy(req("POST", "/api/studio/posts", { body: "{}" }), ["posts"], deps);
    expect(response.status).toBe(504);
    expect(response.headers.get("content-type")).toBe("application/problem+json");
    expect(response.headers.get("retry-after")).toBe("5");
    expect(await response.json()).toEqual({
      type: "about:blank",
      title: "Gateway Timeout",
      status: 504,
      detail: WAKING_UP,
    });
  });

  test("another failure stays the fixed 502 without a detail", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { deps } = setup(() => {
      throw new TypeError("fetch failed");
    });
    const response = await proxy(req("GET", "/api/studio/posts"), ["posts"], deps);
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ type: "about:blank", title: "Bad Gateway", status: 502 });
  });

  test.each([
    [201, "application/json", '{"a":1}'],
    [403, "text/html", "<html>no</html>"],
    [500, "application/problem+json", '{"title":"x"}'],
  ])("an upstream answer %i is logged with its metadata", async (status, type, body) => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const { deps } = setup(
      () =>
        new Response(body, {
          status,
          headers: { "content-type": type, server: "envoy", "www-authenticate": 'Bearer realm="x"' },
        }),
    );
    await proxy(req("POST", "/api/studio/posts"), ["posts"], deps);
    expect(log).toHaveBeenCalledTimes(1);
    expect(log.mock.calls[0][0]).toBe(
      `studio proxy: POST /posts ${status} content-type=${type} length=${body.length} server=envoy www-authenticate=Bearer realm="x"`,
    );
  });

  test("a missing header is logged as a dash and a redirect is logged too", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { deps } = setup(() => new Response(null, { status: 307, headers: { location: "https://elsewhere.example/" } }));
    await proxy(req("GET", "/api/studio/posts"), ["posts"], deps);
    expect(log.mock.calls[0][0]).toBe("studio proxy: GET /posts 307 content-type=- length=0 server=- www-authenticate=-");
  });

  test("the log never holds the token, a cookie, a set-cookie value, a body or odd characters", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const { deps } = setup(
      () =>
        new Response("SECRET-BODY", {
          status: 403,
          headers: { "set-cookie": "session=SECRET-COOKIE", server: `eviléforged ${"x".repeat(300)}` },
        }),
    );
    await proxy(
      req("POST", "/api/studio/posts", { body: "{}", headers: { cookie: "AppServiceAuthSession=SECRET-COOKIE" } }),
      ["posts"],
      deps,
    );
    const line = String(log.mock.calls[0][0]);
    for (const secret of ["tok", "SECRET-COOKIE", "SECRET-BODY"]) expect(line).not.toContain(secret);
    expect(line).toMatch(/^[\x20-\x7e]*$/); // the header's non-ASCII character was replaced
    expect(line).toContain("server=evil?forged ");
    expect(line.length).toBeLessThan(400);
  });
});
