// @vitest-environment node
import { afterEach, expect, test, vi } from "vitest";

import * as route from "./[...path]/route";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

test("the route exports the five methods and never an OPTIONS answer of its own", () => {
  expect(Object.keys(route).sort()).toEqual(["DELETE", "GET", "PATCH", "POST", "PUT", "dynamic"]);
  expect(route.dynamic).toBe("force-dynamic");
});

test("without STUDIO_API_URL it answers a fixed 503", async () => {
  vi.stubEnv("STUDIO_API_URL", "");
  const response = await route.GET(new Request("https://s.example/api/studio/posts"), {
    params: Promise.resolve({ path: ["posts"] }),
  });
  expect(response.status).toBe(503);
  expect(response.headers.get("content-type")).toContain("application/problem+json");
});

test("a path outside the allowlist is a 404 before any token is requested", async () => {
  vi.stubEnv("STUDIO_API_URL", "http://studio-api");
  const response = await route.GET(new Request("https://s.example/api/studio/healthz"), {
    params: Promise.resolve({ path: ["healthz"] }),
  });
  expect(response.status).toBe(404);
});
