import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { ApiError } from "../lib/problem";
import { ProblemList } from "./ProblemList";

afterEach(cleanup);

test("a 403 without a problem body says the studio never saw it", () => {
  render(<ProblemList error={new ApiError(403, null)} />);
  const alert = screen.getByRole("alert");
  expect(alert.textContent).toContain("The request failed (HTTP 403)");
  expect(alert.textContent).toContain("refused before it reached the studio");
});

test.each([502, 503, 504])("a %i without a problem body says the studio is not answering", (status) => {
  render(<ProblemList error={new ApiError(status, null)} />);
  expect(screen.getByRole("alert").textContent).toContain("not answering");
});

test("another status without a body shows no hint", () => {
  render(<ProblemList error={new ApiError(418, null)} />);
  expect(screen.getByRole("alert").textContent).toBe("The request failed (HTTP 418)");
});

test("an error with a problem body is unchanged: title and detail, no hint", () => {
  const problem = { type: "about:blank", title: "Forbidden", status: 403, detail: "origin not allowed" };
  render(<ProblemList error={new ApiError(403, problem)} />);
  expect(screen.getByRole("alert").textContent).toBe("Forbidden origin not allowed");
});

test("the alert is a strip with the problem lines as a bulleted list", () => {
  const problem = {
    type: "about:blank",
    title: "Unprocessable Content",
    status: 422,
    problems: [{ line: 3, message: "raw HTML is not allowed" }],
  };
  render(<ProblemList error={new ApiError(422, problem)} />);
  const alert = screen.getByRole("alert");
  expect(alert.textContent).toBe("Unprocessable ContentLine 3: raw HTML is not allowed");
  expect(alert.querySelector("ul.list-disc li")?.textContent).toBe("Line 3: raw HTML is not allowed");
  expect(alert.className).toContain("border-err");
});

test("the waking-up 504 problem shows its reason", () => {
  const problem = {
    type: "about:blank",
    title: "Gateway Timeout",
    status: 504,
    detail: "The studio API is waking up. Try again in a moment.",
  };
  render(<ProblemList error={new ApiError(504, problem)} />);
  expect(screen.getByRole("alert").textContent).toContain("waking up");
});
