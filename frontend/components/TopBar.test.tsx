import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { createPortal } from "react-dom";

import { TopBar } from "./TopBar";
import { TopBarProvider, useTopBarSlot } from "./TopBarSlot";

const pathname = vi.fn(() => "/");
vi.mock("next/navigation", () => ({ usePathname: () => pathname() }));

afterEach(() => {
  cleanup();
  pathname.mockReset();
});

test("the brand and All posts both link to the list", () => {
  pathname.mockReturnValue("/");
  render(<TopBar />);
  expect(screen.getByRole("link", { name: "Studio" }).getAttribute("href")).toBe("/");
  expect(screen.getByRole("link", { name: "All posts" }).getAttribute("href")).toBe("/");
});

test("All posts is the current page on the list and not on a post", () => {
  pathname.mockReturnValue("/");
  const { unmount } = render(<TopBar />);
  expect(screen.getByRole("link", { name: "All posts" }).getAttribute("aria-current")).toBe("page");
  unmount();
  pathname.mockReturnValue("/posts/01ABC");
  render(<TopBar />);
  expect(screen.getByRole("link", { name: "All posts" }).getAttribute("aria-current")).toBeNull();
});

function Fill() {
  const slot = useTopBarSlot();
  return slot.node ? createPortal(<button>Slot content</button>, slot.node) : null;
}

test("a page can put controls into the bar through the slot", async () => {
  pathname.mockReturnValue("/posts/01ABC");
  render(
    <TopBarProvider>
      <TopBar />
      <Fill />
    </TopBarProvider>,
  );
  const button = await screen.findByRole("button", { name: "Slot content" });
  expect(button.closest("header")).not.toBeNull();
});
