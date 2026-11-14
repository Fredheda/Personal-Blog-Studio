import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import Home from "./page";

vi.mock("../components/Posts", () => ({ Posts: () => <p>posts</p> }));

test("home page names the studio and shows the post list", () => {
  render(<Home />);
  expect(screen.getByRole("heading", { name: "Blog Studio" })).toBeDefined();
  expect(screen.getByText("posts")).toBeDefined();
});
