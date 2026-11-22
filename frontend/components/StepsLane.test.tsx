import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { StepView } from "../lib/steps";
import type { CheckProblem } from "../lib/studio-api";
import { StepsLane } from "./StepsLane";

afterEach(cleanup);

const write: StepView = { marker: "done", text: "Saved 2 min ago" };
const check: StepView & { problems: CheckProblem[] } = {
  marker: "done",
  text: "No problems found",
  problems: [],
};
const publish: StepView & { canUnpublish: boolean } = {
  marker: "active",
  text: "Not published yet. Goes live at /blog/hello",
  canUnpublish: false,
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
      check={{
        marker: "attention",
        text: "2 things to fix before publishing",
        problems: [
          { line: 3, message: "raw HTML is not allowed" },
          { line: 0, message: "slug is required" },
        ],
      }}
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
