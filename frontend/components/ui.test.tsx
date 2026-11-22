import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { Button } from "./Button";
import { MessageStrip } from "./MessageStrip";
import { Pill } from "./Pill";

afterEach(cleanup);

test("a Button is a plain button by default and passes its props on", () => {
  const onClick = vi.fn();
  render(<Button onClick={onClick} disabled>Save</Button>);
  const button = screen.getByRole("button", { name: "Save" }) as HTMLButtonElement;
  expect(button.type).toBe("button");
  expect(button.disabled).toBe(true);
  expect(button.className).not.toContain("bg-primary");
});

test("the primary Button is the white one and a submit type is kept", () => {
  render(<Button variant="primary" type="submit">Create post</Button>);
  const button = screen.getByRole("button", { name: "Create post" }) as HTMLButtonElement;
  expect(button.type).toBe("submit");
  expect(button.className).toContain("bg-primary");
  expect(button.className).toContain("text-primary-ink");
});

test("a Pill shows its words with a ring for a draft and a dot for a published post", () => {
  const { container, rerender } = render(<Pill tone="draft">Draft</Pill>);
  expect(screen.getByText("Draft")).toBeTruthy();
  expect(container.querySelector(".bg-ok")).toBeNull();
  rerender(<Pill tone="published">Published, version 2</Pill>);
  expect(screen.getByText("Published, version 2")).toBeTruthy();
  expect(container.querySelector(".bg-ok")).not.toBeNull();
});

test.each([
  ["conflict", "alert"],
  ["error", "alert"],
  ["success", "status"],
] as const)("a %s strip has the role %s", (kind, role) => {
  render(<MessageStrip kind={kind}>Said it</MessageStrip>);
  expect(screen.getByRole(role).textContent).toBe("Said it");
});

test("a warning strip is an amber alert", () => {
  render(<MessageStrip kind="warning">Not published: fix the problems listed under Check.</MessageStrip>);
  const strip = screen.getByRole("alert");
  expect(strip.className).toContain("border-warn");
  expect(strip.textContent).toBe("Not published: fix the problems listed under Check.");
});

test("a strip shows its action next to the text", () => {
  render(
    <MessageStrip kind="conflict" action={<Button variant="primary">Reload the post</Button>}>
      Changed elsewhere
    </MessageStrip>,
  );
  expect(screen.getByRole("alert").textContent).toContain("Changed elsewhere");
  expect(screen.getByRole("button", { name: "Reload the post" })).toBeTruthy();
});
