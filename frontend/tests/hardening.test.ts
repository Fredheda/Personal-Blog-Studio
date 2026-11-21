// @vitest-environment node
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
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

test("the theme stylesheet loads nothing by URL", () => {
  expect(readFileSync(join(ROOT, "app", "globals.css"), "utf8")).not.toMatch(/url\(/);
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

// --- token.ts is server-only ---

const IMPORT =
  /(?:import|export)\s[^'"]*?from\s*["']([^"']+)["']|import\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)/g;

function resolveLocal(from: string, spec: string, root: string): string | undefined {
  if (!spec.startsWith(".") && !spec.startsWith("@/")) return undefined;
  const base = spec.startsWith("@/") ? resolve(root, spec.slice(2)) : resolve(dirname(from), spec);
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, join(base, "index.ts"), join(base, "index.tsx")]) {
    try {
      if (statSync(candidate).isFile()) return candidate;
    } catch {
      /* not this one */
    }
  }
  return undefined;
}

/** Files that a "use client" file reaches through local imports, any depth. */
function reachableFromClients(root: string): Set<string> {
  const files = walk(root).filter((f) => /\.(ts|tsx)$/.test(f) && !/\.test\.tsx?$/.test(f));
  const isClient = (f: string) => /^\s*["']use client["']/.test(readFileSync(f, "utf8"));
  const seen = new Set<string>();
  const queue = files.filter(isClient);
  while (queue.length > 0) {
    const file = queue.pop()!;
    if (seen.has(file)) continue;
    seen.add(file);
    for (const match of readFileSync(file, "utf8").matchAll(IMPORT)) {
      const target = resolveLocal(file, match[1] ?? match[2] ?? match[3], root);
      if (target !== undefined) queue.push(target);
    }
  }
  return seen;
}

test("lib/token.ts starts with the server-only marker", () => {
  const first = readFileSync(join(ROOT, "lib", "token.ts"), "utf8")
    .split("\n")
    .find((l) => l.trim() !== "");
  expect(first).toBe('import "server-only";');
});

test("no client component reaches lib/token.ts, directly or through other modules", () => {
  const reached = reachableFromClients(ROOT);
  expect([...reached].filter((f) => f.endsWith(join("lib", "token.ts")))).toEqual([]);
});

test("the checker does catch a client file that reaches the token module through another module", () => {
  const dir = mkdtempSync(join(tmpdir(), "client-graph-"));
  mkdirSync(join(dir, "lib"));
  mkdirSync(join(dir, "components"));
  writeFileSync(join(dir, "lib", "token.ts"), 'import "server-only";\nexport const t = 1;\n');
  writeFileSync(join(dir, "lib", "helper.ts"), 'import { t } from "./token";\nexport const h = t;\n');
  writeFileSync(join(dir, "components", "Bad.tsx"), '"use client";\nimport { h } from "../lib/helper";\nexport const B = () => h;\n');
  const reached = reachableFromClients(dir);
  expect([...reached].some((f) => f.endsWith(join("lib", "token.ts")))).toBe(true);
});
