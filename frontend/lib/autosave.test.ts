import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { createAutosave, type AutosaveStatus } from "./autosave";
import { ApiError } from "./problem";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function setup(save: (text: string) => Promise<void>) {
  const statuses: AutosaveStatus[] = [];
  const autosave = createAutosave({ save, delayMs: 1000, onStatus: (s) => statuses.push(s) });
  return { autosave, statuses };
}

test("many edits inside the delay become one save with the latest text", async () => {
  const save = vi.fn(async () => {});
  const { autosave, statuses } = setup(save);
  autosave.push("a");
  autosave.push("ab");
  autosave.push("abc");
  expect(statuses.at(-1)).toBe("pending");
  await vi.advanceTimersByTimeAsync(999);
  expect(save).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(save).toHaveBeenCalledTimes(1);
  expect(save).toHaveBeenCalledWith("abc");
  expect(statuses.at(-1)).toBe("saved");
});

test("an edit during a save is saved after it, never overlapping", async () => {
  const releases: (() => void)[] = [];
  const order: string[] = [];
  const save = vi.fn(async (text: string) => {
    order.push(`start ${text}`);
    await new Promise<void>((resolve) => releases.push(resolve));
    order.push(`end ${text}`);
  });
  const { autosave } = setup(save);
  autosave.push("one");
  await vi.advanceTimersByTimeAsync(1000);
  autosave.push("two");
  await vi.advanceTimersByTimeAsync(5000);
  expect(save).toHaveBeenCalledTimes(1); // "two" waits for "one"
  releases[0]();
  await vi.advanceTimersByTimeAsync(0);
  releases[1]();
  await vi.advanceTimersByTimeAsync(0);
  expect(order).toEqual(["start one", "end one", "start two", "end two"]);
});

test("flush saves pending text now and answers true when it is saved", async () => {
  const save = vi.fn(async () => {});
  const { autosave, statuses } = setup(save);
  autosave.push("draft");
  await expect(autosave.flush()).resolves.toBe(true);
  expect(save).toHaveBeenCalledWith("draft");
  expect(statuses.at(-1)).toBe("saved");
});

test("flush with nothing pending answers true without saving", async () => {
  const save = vi.fn(async () => {});
  const { autosave } = setup(save);
  await expect(autosave.flush()).resolves.toBe(true);
  expect(save).not.toHaveBeenCalled();
});

test("flush clears the debounce timer: a later edit gets the full delay", async () => {
  const save = vi.fn(async () => {});
  const { autosave } = setup(save);
  autosave.push("a");
  await autosave.flush();
  await vi.advanceTimersByTimeAsync(10);
  autosave.push("b");
  await vi.advanceTimersByTimeAsync(999);
  expect(save).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1);
  expect(save).toHaveBeenCalledTimes(2);
});

test("a 412 stops autosave: no retry, flush says no, later edits are not sent", async () => {
  const save = vi.fn(async () => {
    throw new ApiError(412, null);
  });
  const { autosave, statuses } = setup(save);
  autosave.push("a");
  await vi.advanceTimersByTimeAsync(1000);
  expect(statuses.at(-1)).toBe("conflict");
  autosave.push("b");
  await vi.advanceTimersByTimeAsync(5000);
  expect(save).toHaveBeenCalledTimes(1);
  await expect(autosave.flush()).resolves.toBe(false);
});

test("after another failure nothing is re-sent on a timer: the next edit or flush retries", async () => {
  const save = vi.fn().mockRejectedValueOnce(new ApiError(0, null)).mockResolvedValue(undefined);
  const { autosave, statuses } = setup(save);
  autosave.push("keep");
  await vi.advanceTimersByTimeAsync(1000);
  expect(statuses.at(-1)).toBe("error");
  await vi.advanceTimersByTimeAsync(30_000);
  expect(save).toHaveBeenCalledTimes(1); // no timer retry
  autosave.push("keep more");
  await vi.advanceTimersByTimeAsync(1000);
  expect(save).toHaveBeenLastCalledWith("keep more");
  expect(statuses.at(-1)).toBe("saved");
});

test("flush retries the kept text after a failure and answers false while it keeps failing", async () => {
  const save = vi.fn().mockRejectedValue(new ApiError(422, null));
  const { autosave } = setup(save);
  autosave.push("text");
  await vi.advanceTimersByTimeAsync(1000);
  await expect(autosave.flush()).resolves.toBe(false);
  expect(save).toHaveBeenCalledTimes(2);
  expect(save).toHaveBeenLastCalledWith("text");
});

test("close flushes first and only then stops: text typed during an in-flight save is saved too", async () => {
  const releases: (() => void)[] = [];
  const save = vi.fn<(text: string) => Promise<void>>(async () => {
    await new Promise<void>((resolve) => releases.push(resolve));
  });
  const { autosave } = setup(save);
  autosave.push("first");
  await vi.advanceTimersByTimeAsync(1000); // "first" is in flight
  autosave.push("second"); // typed during the save
  const closing = autosave.close();
  releases[0]();
  await vi.advanceTimersByTimeAsync(0);
  releases[1]();
  await expect(closing).resolves.toBe(true);
  expect(save.mock.calls.map((c) => c[0])).toEqual(["first", "second"]);
});

test("stop cancels a pending save and ignores later edits", async () => {
  const save = vi.fn(async () => {});
  const { autosave } = setup(save);
  autosave.push("x");
  autosave.stop();
  autosave.push("y");
  await vi.advanceTimersByTimeAsync(5000);
  expect(save).not.toHaveBeenCalled();
});
