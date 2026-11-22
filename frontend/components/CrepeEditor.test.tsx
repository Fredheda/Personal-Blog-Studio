import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { CrepeEditor, type EditorHandle } from "./CrepeEditor";

afterEach(cleanup);

test("shows the initial Markdown as rich text", async () => {
  const { container } = render(<CrepeEditor initial={"# Hello\n\nSome $x^2$ maths."} onChange={() => {}} />);
  await waitFor(() => expect(container.querySelector(".ProseMirror")).not.toBeNull());
  expect(container.querySelector("h1")?.textContent).toBe("Hello");
});

test("opening a post reports no change, whatever Crepe normalises on load", async () => {
  const onChange = vi.fn();
  const { container } = render(
    <CrepeEditor initial={"# Hello\n\n* a\n* b\n\n| a | b |\n|---|---|\n| 1 | 2 |"} onChange={onChange} />,
  );
  await waitFor(() => expect(container.querySelector(".ProseMirror")).not.toBeNull());
  await new Promise((resolve) => setTimeout(resolve, 100));
  expect(onChange).not.toHaveBeenCalled();
});

test("destroying on unmount does not throw and the host is emptied", async () => {
  const { container, unmount } = render(<CrepeEditor initial="text" onChange={() => {}} />);
  await waitFor(() => expect(container.querySelector(".ProseMirror")).not.toBeNull());
  unmount();
  expect(container.querySelector(".ProseMirror")).toBeNull();
});

async function ready(markdown: string) {
  let handle: EditorHandle | null = null;
  const view = render(<CrepeEditor initial={markdown} onChange={() => {}} onReady={(h) => (handle = h)} />);
  await waitFor(() => expect(handle).not.toBeNull());
  return { ...view, handle: handle as unknown as EditorHandle };
}

const blocks = (container: HTMLElement) =>
  [...(container.querySelector(".ProseMirror")?.children ?? [])].filter((c) => !c.classList.contains("ProseMirror-widget"));

test("jumpToLine puts the caret at the start of the block that holds the line", async () => {
  const text = "# Title\n\nPara\n\n<div>raw</div>\n\nAfter\n";
  const { container, handle } = await ready(text);
  expect(handle.jumpToLine(5, text)).toBe(true);
  expect(blocks(container)[2].contains(window.getSelection()?.anchorNode as Node)).toBe(true);
  expect(handle.jumpToLine(1, text)).toBe(true);
  expect(blocks(container)[0].contains(window.getSelection()?.anchorNode as Node)).toBe(true);
});

test("jumpToLine maps the given text, not the editor's own Markdown", async () => {
  const text = "# T\n\n\n\n\nPara\n\n<div>raw</div>\n\nAfter\n";
  const { container, handle } = await ready(text);
  expect(handle.jumpToLine(8, text)).toBe(true);
  expect(blocks(container)[2].contains(window.getSelection()?.anchorNode as Node)).toBe(true);
});

test("jumpToLine says no for a line the text does not have", async () => {
  const { handle } = await ready("# Title\n");
  expect(handle.jumpToLine(0, "# Title\n")).toBe(false);
});

test("the handle is withdrawn when the editor is destroyed", async () => {
  const onReady = vi.fn();
  const { unmount } = render(<CrepeEditor initial="text" onChange={() => {}} onReady={onReady} />);
  await waitFor(() =>
    expect(onReady).toHaveBeenCalledWith(expect.objectContaining({ jumpToLine: expect.any(Function) })),
  );
  unmount();
  expect(onReady).toHaveBeenLastCalledWith(null);
});
