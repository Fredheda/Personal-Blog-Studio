import { expect, test } from "vitest";

import {
  checkStep,
  publishGate,
  publishStep,
  relativeTime,
  saveEnabled,
  saveKind,
  saveText,
  writeStep,
  type CheckState,
  type SaveKind,
} from "./steps";

const idle = { conflict: false, bodyFailed: false, saving: false, detailsUnsaved: false, bodyPending: false };

test.each([
  [{ conflict: true, bodyFailed: true, saving: true, detailsUnsaved: true, bodyPending: true }, "conflict"],
  [{ ...idle, bodyFailed: true, saving: true, detailsUnsaved: true, bodyPending: true }, "failed"],
  [{ ...idle, saving: true, detailsUnsaved: true, bodyPending: true }, "saving"],
  [{ ...idle, detailsUnsaved: true, bodyPending: true }, "details"],
  [{ ...idle, bodyPending: true }, "pending"],
  [idle, "saved"],
])("save state: the first matching row of spec 7.3 wins (%#)", (input, expected) => {
  expect(saveKind(input)).toBe(expected);
});

test.each([
  ["failed", true],
  ["details", true],
  ["pending", true],
  ["conflict", false],
  ["saving", false],
  ["saved", false],
] as [SaveKind, boolean][])("Save is enabled in %s: %s", (kind, enabled) => {
  expect(saveEnabled(kind)).toBe(enabled);
});

test("save texts follow spec 7.3", () => {
  expect(saveText("conflict", "x")).toBe("Not saved: the post changed elsewhere");
  expect(saveText("failed", "x")).toBe("Not saved");
  expect(saveText("saving", "x")).toBe("Saving…");
  expect(saveText("details", "x")).toBe("Unsaved details");
  expect(saveText("pending", "x")).toBe("Unsaved changes");
  expect(saveText("saved", "2 min ago")).toBe("Saved 2 min ago");
});

test("relative time counts from the given instant", () => {
  const now = Date.parse("2026-11-20T12:00:00Z");
  const ago = (ms: number) => relativeTime(new Date(now - ms).toISOString(), now);
  expect(ago(30_000)).toBe("just now");
  expect(ago(60_000)).toBe("1 min ago");
  expect(ago(2 * 60_000 + 59_000)).toBe("2 min ago");
  expect(ago(3 * 3_600_000)).toBe("3 h ago");
  expect(ago(2 * 86_400_000)).toBe("2 d ago");
  expect(relativeTime("2026-11-20T12:05:00Z", now)).toBe("just now"); // a clock a little ahead
});

test.each([
  ["saved", { marker: "done", text: "Saved 2 min ago" }],
  ["pending", { marker: "active", text: "Unsaved changes" }],
  ["saving", { marker: "active", text: "Saving…" }],
  ["details", { marker: "attention", text: "Unsaved details. Press Save." }],
  ["failed", { marker: "failed", text: "Not saved. Your next edit or Save tries again." }],
  ["conflict", { marker: "failed", text: "Not saved: the post changed elsewhere." }],
] as [SaveKind, object][])("Write step in %s (spec 7.5)", (kind, view) => {
  expect(writeStep(kind, "2 min ago")).toEqual(view);
});

const problems = [
  { line: 3, message: "raw HTML is not allowed" },
  { line: 0, message: "slug is required" },
];

test.each([
  ["pending", { phase: "done", problems: [] }, "waiting", "Waits for a save"],
  ["saved", { phase: "running" }, "active", "Checking…"],
  ["saved", { phase: "done", problems: [] }, "done", "No problems found"],
  ["saved", { phase: "done", problems: [problems[0]] }, "attention", "1 thing to fix before publishing"],
  ["saved", { phase: "done", problems }, "attention", "2 things to fix before publishing"],
  ["saved", { phase: "failed" }, "waiting", "Could not check. The next save tries again."],
] as [SaveKind, CheckState, string, string][])("Check step: %s, %j", (kind, check, marker, text) => {
  const view = checkStep(kind, check);
  expect([view.marker, view.text]).toEqual([marker, text]);
});

test("Check keeps the problems of a finished check and hides them while a save is due", () => {
  expect(checkStep("saved", { phase: "done", problems }).problems).toEqual(problems);
  expect(checkStep("details", { phase: "done", problems }).problems).toEqual([]);
});

const draft = {
  published: false,
  version: null as number | null,
  versionPublishedAt: null as string | null,
  slug: "hello",
};
const clean: CheckState = { phase: "done", problems: [] };

test.each([
  [{ ...draft, published: true, version: 3, versionPublishedAt: "2026-11-09T10:00:00Z" }, "saved", clean,
    "done", "Published, version 3, on 9 Nov. Publish again to send your changes.", true],
  [{ ...draft, published: true, version: 3, versionPublishedAt: "2026-11-09T10:00:00Z" }, "pending", clean,
    "done", "Published, version 3, on 9 Nov. Publish again to send your changes.", true],
  [draft, "pending", clean, "waiting", "Off while something is unsaved", false],
  [draft, "saved", { phase: "done", problems }, "waiting", "Off until the list above is empty", false],
  [draft, "saved", { phase: "running" }, "waiting", "Off until the check is done", false],
  [draft, "saved", clean, "active", "Not published yet. Goes live at /blog/hello", false],
  [draft, "saved", { phase: "failed" }, "active", "Not published yet. Goes live at /blog/hello", false],
  [{ ...draft, slug: "" }, "saved", { phase: "failed" }, "active", "Not published yet.", false],
] as [typeof draft, SaveKind, CheckState, string, string, boolean][])(
  "Publish step %#",
  (post, kind, check, marker, text, canUnpublish) => {
    const view = publishStep(post, kind, check);
    expect([view.marker, view.text, view.canUnpublish]).toEqual([marker, text, canUnpublish]);
  },
);

test.each([
  ["saved", clean, false, { enabled: true }],
  ["saved", { phase: "failed" }, false, { enabled: true }],
  ["saved", clean, true, { enabled: false }],
  ["pending", clean, false, { enabled: false, title: "Save your edits first" }],
  ["conflict", clean, false, { enabled: false }],
  ["saved", { phase: "running" }, false, { enabled: false, title: "Checking…" }],
  ["saved", { phase: "done", problems }, false, { enabled: false, title: "Fix the problems under Check first" }],
] as [SaveKind, CheckState, boolean, object][])("Publish button rule %#", (kind, check, busy, gate) => {
  expect(publishGate({ kind, check, busy })).toEqual(gate);
});
