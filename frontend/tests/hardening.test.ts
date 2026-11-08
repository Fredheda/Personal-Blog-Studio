// @vitest-environment node
import { expect, test } from "vitest";

import nextConfig from "../next.config";

test("every route carries the security headers and no x-powered-by", async () => {
  expect(nextConfig.poweredByHeader).toBe(false);
  const rules = await nextConfig.headers!();
  const everyRoute = rules.find((rule) => rule.source === "/:path*");
  expect(everyRoute).toBeDefined();
  const headers = Object.fromEntries(
    everyRoute!.headers.map((header) => [header.key, header.value]),
  );
  expect(headers).toMatchObject({
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
  });
});
