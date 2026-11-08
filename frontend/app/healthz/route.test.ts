// @vitest-environment node
import { expect, test } from "vitest";

import { GET } from "./route";

test("healthz returns ok and nothing else, uncached", async () => {
  const response = GET();
  expect(response.status).toBe(200);
  expect(await response.json()).toEqual({ status: "ok" });
  expect(response.headers.get("cache-control")).toBe("no-store");
});
