import { Crepe } from "@milkdown/crepe";
import { afterEach, expect, test } from "vitest";

let editor: Crepe | undefined;

afterEach(async () => {
  await editor?.destroy();
  editor = undefined;
  document.body.innerHTML = "";
});

test("Crepe starts in jsdom and serialises headings, maths, code and a table", async () => {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const source = [
    "# Title",
    "",
    "Inline $a^2+b^2=c^2$ maths.",
    "",
    "$$",
    "\\int_0^1 x\\,dx",
    "$$",
    "",
    "```python",
    "print('hi')",
    "```",
    "",
    "| a | b |",
    "| - | - |",
    "| 1 | 2 |",
  ].join("\n");
  editor = new Crepe({ root, defaultValue: source });
  await editor.create();
  const out = editor.getMarkdown();
  expect(out).toContain("# Title");
  expect(out).toContain("$a^2+b^2=c^2$");
  expect(out).toContain("```python");
  expect(out).toMatch(/\|\s*a\s*\|\s*b\s*\|/);
});
