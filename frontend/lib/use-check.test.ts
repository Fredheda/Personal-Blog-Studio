import { act, renderHook, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { CheckResult, StudioApi } from "./studio-api";
import { useCheck } from "./use-check";

const etags = { bodyEtag: '"b1"', metaEtag: '"m1"' };
const answer = (over: Partial<CheckResult> = {}): CheckResult => ({ ok: true, problems: [], ...etags, ...over });
const apiWith = (checkPost: StudioApi["checkPost"]) => ({ checkPost }) as StudioApi;

function run(api: StudioApi, props: { ready?: boolean; saves?: number } = {}) {
  return renderHook(
    (p: { ready: boolean; saves: number }) =>
      useCheck({ api, id: "p1", ready: p.ready, saves: p.saves, current: () => etags }),
    { initialProps: { ready: props.ready ?? true, saves: props.saves ?? 0 } },
  );
}

test("checks once the post is loaded and reports the problems", async () => {
  const checkPost = vi.fn(async () => answer({ ok: false, problems: [{ line: 3, message: "raw HTML is not allowed" }] }));
  const { result } = run(apiWith(checkPost));
  expect(result.current).toEqual({ phase: "running" });
  await waitFor(() => expect(result.current).toEqual({ phase: "done", problems: [{ line: 3, message: "raw HTML is not allowed" }] }));
  expect(checkPost).toHaveBeenCalledWith("p1");
});

test("does not ask before the post is loaded", () => {
  const checkPost = vi.fn(async () => answer());
  run(apiWith(checkPost), { ready: false });
  expect(checkPost).not.toHaveBeenCalled();
});

test("asks again after a save and shows running until that answer arrives", async () => {
  const checkPost = vi.fn(async () => answer());
  const { result, rerender } = run(apiWith(checkPost));
  await waitFor(() => expect(result.current.phase).toBe("done"));
  rerender({ ready: true, saves: 1 });
  expect(result.current).toEqual({ phase: "running" });
  await waitFor(() => expect(result.current.phase).toBe("done"));
  expect(checkPost).toHaveBeenCalledTimes(2);
});

test("an answer for older ETags is dropped", async () => {
  const stale = vi.fn(async () => answer({ bodyEtag: '"b0"' }));
  const { result } = run(apiWith(stale));
  await waitFor(() => expect(stale).toHaveBeenCalled());
  await act(async () => {});
  expect(result.current).toEqual({ phase: "running" });
});

test("only the latest request counts: a slow first answer cannot overwrite the second", async () => {
  let release: (value: CheckResult) => void = () => {};
  const first = new Promise<CheckResult>((resolve) => (release = resolve));
  const checkPost = vi
    .fn<StudioApi["checkPost"]>()
    .mockReturnValueOnce(first)
    .mockResolvedValueOnce(answer({ problems: [{ line: 1, message: "second" }] }));
  const { result, rerender } = run(apiWith(checkPost));
  rerender({ ready: true, saves: 1 });
  await waitFor(() => expect(result.current).toEqual({ phase: "done", problems: [{ line: 1, message: "second" }] }));
  release(answer({ problems: [{ line: 9, message: "first" }] }));
  await act(async () => {});
  expect(result.current).toEqual({ phase: "done", problems: [{ line: 1, message: "second" }] });
});

test("a failed request says so, and the next save asks again", async () => {
  const checkPost = vi
    .fn<StudioApi["checkPost"]>()
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(answer());
  const { result, rerender } = run(apiWith(checkPost));
  await waitFor(() => expect(result.current).toEqual({ phase: "failed" }));
  rerender({ ready: true, saves: 1 });
  await waitFor(() => expect(result.current).toEqual({ phase: "done", problems: [] }));
});
