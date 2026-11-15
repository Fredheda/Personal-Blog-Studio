import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { CrepeEditor } from "./CrepeEditor";

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
