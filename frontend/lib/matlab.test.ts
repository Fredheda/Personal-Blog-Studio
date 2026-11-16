import { LanguageDescription } from "@codemirror/language";
import { expect, test } from "vitest";

import { matlab } from "./matlab";

test("MATLAB is found by name, alias and the .m extension", () => {
  expect(matlab).toBeInstanceOf(LanguageDescription);
  expect(LanguageDescription.matchLanguageName([matlab], "matlab", true)).toBe(matlab);
  expect(LanguageDescription.matchFilename([matlab], "solve.m")).toBe(matlab);
});

test("it loads a working language (the Octave mode)", async () => {
  const support = await matlab.load();
  expect(support.language).toBeDefined();
});
