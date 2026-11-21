import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { TopBar } from "./TopBar";

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
