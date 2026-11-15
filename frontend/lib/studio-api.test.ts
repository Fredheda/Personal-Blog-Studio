// @vitest-environment node
import { expect, test, vi } from "vitest";

import { ApiError } from "./problem";
import { createStudioApi } from "./studio-api";

function mock(response: Response) {
  const fetchImpl = vi.fn(async () => response) as unknown as typeof fetch;
  return { api: createStudioApi(fetchImpl), fetchImpl: fetchImpl as unknown as ReturnType<typeof vi.fn> };
}

test("every call goes to /api/studio with the custom header and no cache", async () => {
  const { api, fetchImpl } = mock(Response.json({ items: [] }));
  await api.listPosts();
  const [url, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/studio/posts");
  expect(new Headers(init.headers).get("x-blog-studio")).toBe("1");
  expect(init.cache).toBe("no-store");
});

test("saving the body sends PUT with the ETag in If-Match, quotes kept", async () => {
  const { api, fetchImpl } = mock(Response.json({ postId: "ID", body: "b", bodyEtag: '"2"', metaEtag: '"1"' }));
  await api.saveBody("ID", "b", '"1"');
  const [url, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/studio/posts/ID/body");
  expect(init.method).toBe("PUT");
  expect(new Headers(init.headers).get("if-match")).toBe('"1"');
  expect(JSON.parse(init.body as string)).toEqual({ body: "b" });
});

test("patching metadata sends only the given fields as camelCase JSON", async () => {
  const { api, fetchImpl } = mock(Response.json({ postId: "ID" }));
  await api.patchMeta("ID", { title: "T", clearCover: true }, '"m"');
  const [, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body as string)).toEqual({ title: "T", clearCover: true });
});

test("a 204 answers undefined", async () => {
  const { api } = mock(new Response(null, { status: 204 }));
  await expect(api.unpublish("ID")).resolves.toBeUndefined();
});

test("a problem response becomes an ApiError with its status and problem lines", async () => {
  const body = { type: "about:blank", title: "Unprocessable Content", status: 422, problems: [{ line: 3, message: "raw HTML is not allowed" }] };
  const { api } = mock(new Response(JSON.stringify(body), { status: 422, headers: { "content-type": "application/problem+json" } }));
  const error = await api.publish("ID", '"1"').catch((e) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(422);
  expect(error.problem.problems).toEqual([{ line: 3, message: "raw HTML is not allowed" }]);
});

test("a fetch that fails outright (offline, or the sign-in redirect) is an ApiError with status 0", async () => {
  const fetchImpl = vi.fn(async () => {
    throw new TypeError("Failed to fetch");
  }) as unknown as typeof fetch;
  const error = await createStudioApi(fetchImpl).listPosts().catch((e) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(0);
});

test("a non-JSON failure still becomes an ApiError", async () => {
  const { api } = mock(new Response("<html>bad gateway</html>", { status: 502 }));
  const error = await api.getPost("ID").catch((e) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(502);
  expect(error.problem).toBeNull();
});
