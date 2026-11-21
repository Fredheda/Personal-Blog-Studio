import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { Dialog } from "./Dialog";

afterEach(cleanup);

function setup() {
  const onCancel = vi.fn();
  const onConfirm = vi.fn();
  render(
    <Dialog title="Delete this draft?" cancelLabel="Keep it" confirmLabel="Delete draft" onCancel={onCancel} onConfirm={onConfirm}>
      {'"First" is removed.'}
    </Dialog>,
  );
  return { onCancel, onConfirm };
}

test("the dialog is named by its title, shows its text and starts on the cautious button", () => {
  setup();
  const dialog = screen.getByRole("dialog", { name: "Delete this draft?" });
  expect(dialog.getAttribute("aria-modal")).toBe("true");
  expect(dialog.getAttribute("aria-describedby")).toBeTruthy();
  expect(document.getElementById(dialog.getAttribute("aria-describedby") as string)?.textContent).toContain("is removed.");
  expect(dialog.textContent).toContain('"First" is removed.');
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Keep it" }));
});

test("the two buttons call their own handler", () => {
  const { onCancel, onConfirm } = setup();
  fireEvent.click(screen.getByRole("button", { name: "Delete draft" }));
  expect(onConfirm).toHaveBeenCalledTimes(1);
  expect(onCancel).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
  expect(onCancel).toHaveBeenCalledTimes(1);
});

test("Escape and a click on the backdrop are the cautious action; a click inside is not", () => {
  const { onCancel, onConfirm } = setup();
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(onCancel).toHaveBeenCalledTimes(1);
  fireEvent.mouseDown(screen.getByRole("dialog").parentElement as HTMLElement);
  expect(onCancel).toHaveBeenCalledTimes(2);
  fireEvent.mouseDown(screen.getByRole("dialog"));
  expect(onCancel).toHaveBeenCalledTimes(2);
  expect(onConfirm).not.toHaveBeenCalled();
});

test("Tab stays inside the dialog", () => {
  setup();
  const keep = screen.getByRole("button", { name: "Keep it" });
  const confirm = screen.getByRole("button", { name: "Delete draft" });
  confirm.focus();
  fireEvent.keyDown(confirm, { key: "Tab" });
  expect(document.activeElement).toBe(keep);
  fireEvent.keyDown(keep, { key: "Tab", shiftKey: true });
  expect(document.activeElement).toBe(confirm);
});

test("focus returns to the element that had it before the dialog opened", () => {
  const opener = document.createElement("button");
  document.body.appendChild(opener);
  opener.focus();
  const { unmount } = render(
    <Dialog title="T" cancelLabel="Keep it" confirmLabel="Go" onCancel={() => {}} onConfirm={() => {}}>
      x
    </Dialog>,
  );
  expect(document.activeElement).not.toBe(opener);
  unmount();
  expect(document.activeElement).toBe(opener);
  opener.remove();
});
