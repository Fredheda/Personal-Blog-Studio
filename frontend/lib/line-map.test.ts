import { readFileSync } from "node:fs";
import { expect, test } from "vitest";

import { blockStartLines, jumpTarget } from "./line-map";

const fixture = (name: string) => readFileSync(`tests/fixtures/crepe-output/${name}`, "utf8");

test("block start lines of the editor fixtures", () => {
  expect(blockStartLines(fixture("basic.md"))).toEqual([1, 3, 5, 7, 10, 13, 15]);
  expect(blockStartLines(fixture("maths-code-table.md"))).toEqual([1, 3, 5, 9, 13, 17]);
});

test("a raw HTML block is a block of its own", () => {
  expect(blockStartLines("# T\n\ntext\n\n<div>raw</div>\n\nafter\n")).toEqual([1, 3, 5, 7]);
});

test("a link reference definition draws nothing in the editor, so it is not a block", () => {
  expect(blockStartLines("text [a]\n\n[a]: https://example.com\n\nafter\n")).toEqual([1, 5]);
});

const md = "# T\n\ntext\n\n<div>raw</div>\n\nafter\n";

test.each([
  [1, 0],
  [2, 0],
  [3, 1],
  [4, 1],
  [5, 2],
  [7, 3],
  [99, 3],
])("line %i is in block %i", (line, block) => {
  expect(jumpTarget(md, line, 4)).toBe(block);
});

test("the editor may draw one empty paragraph after the last block", () => {
  expect(jumpTarget(md, 5, 5)).toBe(2);
});

test("blocks that do not line up with the Markdown are not trusted", () => {
  expect(jumpTarget(md, 5, 3)).toBeNull();
  expect(jumpTarget(md, 5, 6)).toBeNull();
});

test("there is nothing to jump to without a line or without blocks", () => {
  expect(jumpTarget(md, 0, 4)).toBeNull();
  expect(jumpTarget("", 1, 1)).toBeNull();
});
