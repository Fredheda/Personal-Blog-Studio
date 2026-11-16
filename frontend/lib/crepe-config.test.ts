import { Crepe } from "@milkdown/crepe";
import { expect, test } from "vitest";

import { crepeFeatureConfigs, crepeFeatures } from "./crepe-config";
import { matlab } from "./matlab";

test("the image block and the AI feature are off, the text blocks are on", () => {
  expect(crepeFeatures[Crepe.Feature.ImageBlock]).toBe(false);
  expect(crepeFeatures[Crepe.Feature.AI]).toBe(false);
  const features = crepeFeatures as Record<string, unknown>;
  for (const on of [Crepe.Feature.CodeMirror, Crepe.Feature.Table, Crepe.Feature.Latex, Crepe.Feature.Toolbar, Crepe.Feature.BlockEdit]) {
    expect(features[on]).not.toBe(false);
  }
});

test("maths renders as MathML and never throws on bad input", () => {
  const latex = crepeFeatureConfigs[Crepe.Feature.Latex];
  expect(latex.katexOptions).toMatchObject({ output: "mathml", throwOnError: false });
});

test("code blocks offer MATLAB next to the stock languages", () => {
  const code = crepeFeatureConfigs[Crepe.Feature.CodeMirror];
  expect(code.languages).toContain(matlab);
  expect(code.languages.some((l) => l.name === "Python")).toBe(true);
});
