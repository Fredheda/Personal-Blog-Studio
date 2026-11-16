import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { Preview } from "./Preview";

afterEach(cleanup);

test("renders headings, tables and code from Markdown", () => {
  const { container } = render(<Preview markdown={"# Title\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```python\nprint(1)\n```"} />);
  expect(container.querySelector("h1")?.textContent).toBe("Title");
  expect(container.querySelector("table")).not.toBeNull();
  expect(container.querySelector("pre code")?.textContent).toContain("print(1)");
});

test("maths becomes MathML and never KaTeX HTML", () => {
  const { container } = render(<Preview markdown={"Inline $a^2$ and\n\n$$\n\\int_0^1 x\\,dx\n$$"} />);
  expect(container.querySelectorAll("math").length).toBeGreaterThanOrEqual(2);
  expect(container.querySelector(".katex-html")).toBeNull();
});

test("raw HTML in the Markdown is not rendered", () => {
  const { container } = render(<Preview markdown={"<script>alert(1)</script><img src=x onerror=alert(1)>\n\n<b>bold</b>"} />);
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("b")).toBeNull();
});

test("Markdown image syntax draws no img element: nothing is fetched until media exists", () => {
  const { container } = render(<Preview markdown={"![alt text](https://tracker.example/pixel.png)\n\n![local](media:abc)"} />);
  expect(container.querySelector("img")).toBeNull();
  expect(container.textContent).toContain("alt text");
});

test("a javascript: link is not turned into a live link", () => {
  const { container } = render(<Preview markdown={"[x](javascript:alert(1))"} />);
  const href = container.querySelector("a")?.getAttribute("href") ?? "";
  expect(href).not.toMatch(/^\s*(javascript|data|vbscript):/i);
});
