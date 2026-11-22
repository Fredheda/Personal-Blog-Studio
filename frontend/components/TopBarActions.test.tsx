import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { TopBarActions } from "./TopBarActions";

afterEach(cleanup);

const base = {
  kind: "saved" as const,
  ago: "just now",
  previewOn: false,
  onPreview: () => {},
  canSave: false,
  onSave: () => {},
  publish: { enabled: true },
  onPublish: () => {},
};

test("shows the save state as text", () => {
  render(<TopBarActions {...base} kind="details" />);
  expect(screen.getByRole("status").textContent).toBe("Unsaved details");
});

test("shows when it was saved", () => {
  render(<TopBarActions {...base} ago="2 min ago" />);
  expect(screen.getByRole("status").textContent).toBe("Saved 2 min ago");
});

test("Save is dimmed with its reason when there is nothing to save, and calls out when there is", () => {
  const onSave = vi.fn();
  const { rerender } = render(<TopBarActions {...base} onSave={onSave} />);
  const save = screen.getByRole("button", { name: "Save" }) as HTMLButtonElement;
  expect(save.disabled).toBe(true);
  expect(save.title).toBe("Nothing to save");
  rerender(<TopBarActions {...base} canSave onSave={onSave} />);
  expect(save.disabled).toBe(false);
  expect(save.className).toContain("border-primary");
  fireEvent.click(save);
  expect(onSave).toHaveBeenCalledOnce();
});

test("Publish is white, and dimmed with the reason it is off", () => {
  const onPublish = vi.fn();
  const { rerender } = render(<TopBarActions {...base} onPublish={onPublish} />);
  const publish = screen.getByRole("button", { name: "Publish" }) as HTMLButtonElement;
  expect(publish.className).toContain("bg-primary");
  fireEvent.click(publish);
  expect(onPublish).toHaveBeenCalledOnce();
  rerender(<TopBarActions {...base} publish={{ enabled: false, title: "Save your edits first" }} />);
  expect(publish.disabled).toBe(true);
  expect(publish.title).toBe("Save your edits first");
});

test("Preview is a toggle", () => {
  const onPreview = vi.fn();
  const { rerender } = render(<TopBarActions {...base} onPreview={onPreview} />);
  const preview = screen.getByRole("button", { name: "Preview" });
  expect(preview.getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(preview);
  expect(onPreview).toHaveBeenCalledOnce();
  rerender(<TopBarActions {...base} previewOn />);
  expect(preview.getAttribute("aria-pressed")).toBe("true");
});
