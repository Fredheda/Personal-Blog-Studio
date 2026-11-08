// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "vitest";

import nextConfig from "../next.config";

const ROOT = fileURLToPath(new URL("..", import.meta.url));

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    if (["node_modules", ".next"].includes(name)) return [];
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

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

test("no font files are bundled", () => {
  const fonts = walk(ROOT).filter((file) => /\.(woff2?|ttf|otf|eot)$/i.test(file));
  expect(fonts).toEqual([]);
});

test("no web-font loading in source", () => {
  const sources = walk(ROOT).filter(
    (file) => /\.(css|tsx?|mjs)$/.test(file) && !file.endsWith("hardening.test.ts"),
  );
  const loader =
    /@font-face|next\/font|fonts\.googleapis|fonts\.gstatic|fontsource|typekit|fonts\.bunny/;
  const offenders = sources.filter((file) => loader.test(readFileSync(file, "utf8")));
  expect(offenders).toEqual([]);
});

test("Dockerfile runs as a non-root user and serves the standalone build", () => {
  const text = readFileSync(join(ROOT, "Dockerfile"), "utf8");
  expect(text).toMatch(/^USER node$/m);
  expect(text).toContain(".next/standalone");
  expect(text).toContain('CMD ["node", "server.js"]');
  expect(text).toContain("EXPOSE 3000");
});
