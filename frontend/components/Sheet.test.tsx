import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { Sheet } from "./Sheet";

afterEach(cleanup);

test("shows its title and content as a modal sheet", () => {
  render(
    <Sheet title="Check" onClose={() => {}}>
      <p>Two problems</p>
    </Sheet>,
  );
  const dialog = screen.getByRole("dialog", { name: "Check" });
  expect(dialog.getAttribute("aria-modal")).toBe("true");
  expect(dialog.textContent).toContain("Two problems");
});

test("Close, Esc and a click on the backdrop close it; a click on the panel does not", () => {
  const onClose = vi.fn();
  render(
    <Sheet title="Check" onClose={onClose}>
      text
    </Sheet>,
  );
  fireEvent.mouseDown(screen.getByRole("dialog"));
  expect(onClose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  fireEvent.mouseDown(screen.getByRole("dialog").parentElement as HTMLElement);
  expect(onClose).toHaveBeenCalledTimes(3);
});

test("focus starts on Close, stays inside, and returns to where it was", () => {
  const opener = document.createElement("button");
  document.body.append(opener);
  opener.focus();
  const { unmount } = render(
    <Sheet title="Check" onClose={() => {}}>
      <button>First</button>
    </Sheet>,
  );
  const close = screen.getByRole("button", { name: "Close" });
  expect(document.activeElement).toBe(close);
  screen.getByRole("button", { name: "First" }).focus();
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Tab" });
  expect(document.activeElement).toBe(close);
  unmount();
  expect(document.activeElement).toBe(opener);
  opener.remove();
});
