// @vitest-environment node
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, test } from "vitest";

import { findFonts } from "./check-no-fonts.mjs";

function tree(files: string[]): string {
  const root = mkdtempSync(join(tmpdir(), "static-"));
  for (const file of files) {
    const path = join(root, file);
    mkdirSync(join(path, ".."), { recursive: true });
    writeFileSync(path, "x");
  }
  return root;
}

test("a clean static folder has no fonts", () => {
  expect(findFonts(tree(["chunks/a.js", "css/a.css", "media/logo.svg"]))).toEqual([]);
});

test("every font extension is found, nested, in any case", () => {
  const found = findFonts(tree(["media/a.woff", "media/b.WOFF2", "x/y/c.ttf", "d.otf"]));
  expect(found.map((f: string) => f.split(/[\\/]/).pop()).sort()).toEqual(["a.woff", "b.WOFF2", "c.ttf", "d.otf"]);
});

test("a missing folder is not an error (nothing was built)", () => {
  expect(findFonts(join(tmpdir(), "does-not-exist-xyz"))).toEqual([]);
});
