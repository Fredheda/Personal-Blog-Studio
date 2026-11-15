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

test("the editor brings no font: no @font-face or url() in Crepe's theme CSS and no KaTeX CSS import", () => {
  const theme = join(ROOT, "node_modules", "@milkdown", "crepe", "lib", "theme");
  const cssFiles = walk(theme).filter((f) => f.endsWith(".css"));
  expect(cssFiles.length).toBeGreaterThan(0);
  for (const file of cssFiles) {
    const css = readFileSync(file, "utf8");
    expect(css, file).not.toMatch(/@font-face/);
    expect(css, file).not.toMatch(/url\(/);
  }
  const sources = [...walk(join(ROOT, "app")), ...walk(join(ROOT, "components")), ...walk(join(ROOT, "lib"))].filter(
    (f) => /\.(ts|tsx|css)$/.test(f) && !/\.test\.tsx?$/.test(f),
  );
  for (const file of sources) {
    expect(readFileSync(file, "utf8"), file).not.toMatch(/katex(\.min)?\.css|katex\/dist/);
    // Crepe's aggregate and latex theme files @import KaTeX's stylesheet, which
    // brings its font files; only the individual parts are allowed.
    expect(readFileSync(file, "utf8"), file).not.toMatch(/crepe\/theme\/common\/(style|latex)\.css/);
  }
});

test("the theme part that imports KaTeX's stylesheet is still the only one, so skipping it is enough", () => {
  const common = join(ROOT, "node_modules", "@milkdown", "crepe", "lib", "theme");
  const importing = walk(common)
    .filter((f) => f.endsWith(".css"))
    .filter((f) => /@import\s+['"]katex/.test(readFileSync(f, "utf8")))
    .map((f) => f.split(/[\\/]/).pop());
  expect(importing).toEqual(["latex.css"]);
});

test("every response carries a CSP that stops remote images and media", async () => {
  const rules = await nextConfig.headers!();
  const everyRoute = rules.find((rule) => rule.source === "/:path*")!;
  const csp = everyRoute.headers.find((h) => h.key === "Content-Security-Policy");
  expect(csp?.value).toBe("img-src 'self' data: blob:; media-src 'self'");
});
