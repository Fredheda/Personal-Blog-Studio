import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { StepView } from "../lib/steps";
import type { CheckProblem } from "../lib/studio-api";
import { StepChips, StepsLane } from "./StepsLane";

afterEach(cleanup);

const write: StepView = { marker: "done", text: "Saved 2 min ago", chip: "Saved" };
const check: StepView & { problems: CheckProblem[] } = {
  marker: "done",
  text: "No problems found",
  chip: "No problems",
  problems: [],
};
const publish: StepView & { canUnpublish: boolean } = {
  marker: "active",
  text: "Not published yet. Goes live at /blog/hello",
  chip: "Not published",
  canUnpublish: false,
};
const withProblems: StepView & { problems: CheckProblem[] } = {
  marker: "attention",
  text: "2 things to fix before publishing",
  chip: "2 to fix",
  problems: [
    { line: 3, message: "raw HTML is not allowed" },
    { line: 0, message: "slug is required" },
  ],
};

function steps() {
  return within(screen.getByRole("list", { name: "Steps" })).getAllByRole("listitem");
}

test("lists Write, Check and Publish in order with their text and marker", () => {
  render(<StepsLane write={write} check={check} publish={publish} onUnpublish={() => {}} />);
  const [one, two, three] = steps();
  expect(one.textContent).toContain("1 Write");
  expect(one.textContent).toContain("Saved 2 min ago");
  expect(one.querySelector("[data-marker]")?.getAttribute("data-marker")).toBe("done");
  expect(two.textContent).toContain("2 Check");
  expect(three.textContent).toContain("3 Publish");
  expect(three.querySelector("[data-marker]")?.getAttribute("data-marker")).toBe("active");
});

test("each marker has its own look", () => {
  const { container, rerender } = render(
    <StepsLane
      write={{ ...write, marker: "attention" }}
      check={{ ...check, marker: "failed" }}
      publish={{ ...publish, marker: "waiting" }}
      onUnpublish={() => {}}
    />,
  );
  const looks = [...container.querySelectorAll("[data-marker]")].map((m) => m.className);
  expect(looks[0]).toContain("border-warn");
  expect(looks[1]).toContain("border-err");
  expect(looks[2]).toContain("border-muted");
  rerender(<StepsLane write={write} check={check} publish={{ ...publish, marker: "active" }} onUnpublish={() => {}} />);
  const markers = container.querySelectorAll("[data-marker]");
  expect(markers[0].className).toContain("bg-ok");
  expect(markers[2].className).toContain("border-primary");
});

test("a problem is a card with its line; a problem without a line shows the message with a capital", () => {
  render(
    <StepsLane
      write={write}
      check={withProblems}
      publish={publish}
      onUnpublish={() => {}}
    />,
  );
  expect(screen.getByText("Line 3").textContent).toBe("Line 3");
  expect(screen.getByText(/raw HTML is not allowed/)).toBeTruthy();
  expect(screen.getByText("Slug is required")).toBeTruthy();
  expect(screen.queryByText(/Line 0/)).toBeNull();
});

test("Unpublish is a link in the Publish step only for a published post, and asks to unpublish", () => {
  const onUnpublish = vi.fn();
  const { rerender } = render(<StepsLane write={write} check={check} publish={publish} onUnpublish={onUnpublish} />);
  expect(screen.queryByRole("button", { name: "Unpublish" })).toBeNull();
  rerender(
    <StepsLane
      write={write}
      check={check}
      publish={{ ...publish, marker: "done", canUnpublish: true }}
      onUnpublish={onUnpublish}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Unpublish" }));
  expect(onUnpublish).toHaveBeenCalledOnce();
});

test("a problem with a line is a button when a jump is possible; a problem without a line never is", () => {
  const onJump = vi.fn();
  render(<StepsLane write={write} check={withProblems} publish={publish} onJump={onJump} onUnpublish={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: /Line 3/ }));
  expect(onJump).toHaveBeenCalledWith(3);
  expect(screen.queryByRole("button", { name: /Slug is required/ })).toBeNull();
});

test("without a jump the cards are plain text", () => {
  render(<StepsLane write={write} check={withProblems} publish={publish} onUnpublish={() => {}} />);
  expect(screen.queryByRole("button", { name: /Line 3/ })).toBeNull();
});

const chips = (over: { check?: typeof check; publish?: typeof publish } = {}) => (
  <StepChips
    write={write}
    check={over.check ?? check}
    publish={over.publish ?? publish}
    onOpenProblems={onOpenProblems}
    onOpenPublish={onOpenPublish}
  />
);
const onOpenProblems = vi.fn();
const onOpenPublish = vi.fn();

test("the chip strip shows the three steps; the Check chip is a button only with problems", () => {
  const { rerender } = render(chips());
  const strip = screen.getByRole("group", { name: "Steps summary" });
  expect(strip.textContent).toBe("1 Saved2 No problems3 Not published");
  expect(screen.queryByRole("button", { name: /No problems/ })).toBeNull();
  rerender(chips({ check: withProblems }));
  fireEvent.click(screen.getByRole("button", { name: "2 2 to fix" }));
  expect(onOpenProblems).toHaveBeenCalledOnce();
});

test("the Publish chip is a button that opens the Publish sheet", () => {
  onOpenPublish.mockClear();
  render(chips());
  fireEvent.click(screen.getByRole("button", { name: "3 Not published" }));
  expect(onOpenPublish).toHaveBeenCalledOnce();
});

test("each chip carries its step's marker colour", () => {
  const { container } = render(
    <StepChips
      write={{ ...write, marker: "failed" }}
      check={{ ...check, marker: "attention" }}
      publish={{ ...publish, marker: "waiting" }}
      onOpenProblems={() => {}}
      onOpenPublish={() => {}}
    />,
  );
  const looks = [...container.querySelectorAll("[data-marker]")].map((m) => m.className);
  expect(looks[0]).toContain("border-err");
  expect(looks[1]).toContain("border-warn");
  expect(looks[2]).toContain("border-muted");
});
