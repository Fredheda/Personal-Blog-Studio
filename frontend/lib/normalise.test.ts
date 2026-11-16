import { expect, test } from "vitest";

import { normaliseMarkdown } from "./normalise";

test("an HTML line break at the end of a line becomes a backslash break", () => {
  expect(normaliseMarkdown("first<br />\nsecond")).toBe("first\\\nsecond");
  expect(normaliseMarkdown("first<br>\nsecond")).toBe("first\\\nsecond");
  expect(normaliseMarkdown("first<br/>\nsecond")).toBe("first\\\nsecond");
});

test("a line break in the middle of a line splits the line with a backslash break", () => {
  expect(normaliseMarkdown("one<br />two")).toBe("one\\\ntwo");
});

test("a break inside a table cell becomes a space", () => {
  expect(normaliseMarkdown("| a<br />b | c |\n| - | - |\n| 1 | 2 |")).toBe("| a b | c |\n| - | - |\n| 1 | 2 |");
});

test("a paragraph that is only a break becomes an empty line", () => {
  expect(normaliseMarkdown("one\n\n<br />\n\ntwo")).toBe("one\n\n\n\ntwo");
});

test("code fences are left alone, including a literal <br /> in code", () => {
  const code = "```html\n<p>one<br />two</p>\n```";
  expect(normaliseMarkdown(code)).toBe(code);
  expect(normaliseMarkdown("`<br />` in text")).toBe("`<br />` in text");
});

test("Markdown without any break is unchanged", () => {
  const text = "# Title\n\nSome *text* with $x^2$.\n\n| a | b |\n| - | - |\n| 1 | 2 |\n";
  expect(normaliseMarkdown(text)).toBe(text);
});
