// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "vitest";

import { contrastRatio, themeColors } from "./contrast";

const css = readFileSync(fileURLToPath(new URL("../app/globals.css", import.meta.url)), "utf8");
const colors = themeColors(css);

test("the contrast function knows black on white is 21", () => {
  expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 5);
});

// The pairs of spec section 7.1: text on its backgrounds.
const PAIRS: [string, string][] = [
  ["text", "bg"], ["text", "pane"], ["text", "raise"],
  ["ink", "bg"],
  ["muted", "bg"], ["muted", "deep"], ["muted", "pane"], ["muted", "raise"],
  ["ok", "bg"], ["warn", "bg"], ["err", "bg"],
  ["ok-ink", "ok"], ["primary-ink", "primary"],
  ["code-ink", "deep"], ["code-keyword", "deep"], ["code-function", "deep"],
  ["code-number", "deep"], ["code-comment", "deep"],
  ["code-ink", "raise"], // inline code in the Preview and the editor
];

test.each(PAIRS)("%s on %s has a contrast of at least 4.5", (foreground, background) => {
  expect(colors[foreground], `--color-${foreground} is missing`).toBeDefined();
  expect(colors[background], `--color-${background} is missing`).toBeDefined();
  expect(contrastRatio(colors[foreground], colors[background])).toBeGreaterThanOrEqual(4.5);
});

test("the spec's figures hold (text on bg 16.9, muted on bg 7.2, comment on deep 5.4)", () => {
  expect(contrastRatio(colors.text, colors.bg)).toBeCloseTo(16.9, 0);
  expect(contrastRatio(colors.muted, colors.bg)).toBeCloseTo(7.2, 0);
  expect(contrastRatio(colors["code-comment"], colors.deep)).toBeCloseTo(5.4, 0);
});
