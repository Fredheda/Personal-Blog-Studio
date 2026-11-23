import { act, cleanup, render, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useController } from "./useController";
import { useInterval } from "./useInterval";
import { useRequest } from "./useRequest";
import { useWidget } from "./useWidget";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("useInterval", () => {
  it("runs the function on every tick and stops on unmount", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const { unmount } = renderHook(() => useInterval(fn, 1000));
    vi.advanceTimersByTime(2000);
    expect(fn).toHaveBeenCalledTimes(2);
    unmount();
    vi.advanceTimersByTime(5000);
    expect(fn).toHaveBeenCalledTimes(2);
  });
});

describe("useRequest", () => {
  it("does not report a late failure of a request whose key has changed", async () => {
    let rejectOld!: (error: unknown) => void;
    const old = new Promise<string>((_resolve, reject) => {
      rejectOld = reject;
    });
    const onError = vi.fn();
    const { rerender } = renderHook(
      ({ key }) =>
        useRequest(() => (key === "old" ? old : Promise.resolve("new")), key, {
          onResult: vi.fn(),
          onError,
        }),
      { initialProps: { key: "old" } },
    );
    rerender({ key: "new" });
    await act(async () => {});
    rejectOld(new Error("late"));
    await act(async () => {});
    expect(onError).not.toHaveBeenCalled();
  });
});

describe("useController", () => {
  it("creates one controller per key, closes it on a new key and on unmount", () => {
    const closes: string[] = [];
    const seen: Array<() => boolean> = [];
    const create = (name: string) => (alive: () => boolean) => {
      seen.push(alive);
      return { name, close: () => closes.push(name) };
    };
    const { result, rerender, unmount } = renderHook(
      ({ key }) => useController(create(key), key),
      { initialProps: { key: "a" } },
    );
    expect(result.current.current?.name).toBe("a");
    rerender({ key: "a" });
    expect(closes).toEqual([]);
    rerender({ key: "b" });
    expect(closes).toEqual(["a"]);
    expect(seen[0]()).toBe(false);
    expect(seen[1]()).toBe(true);
    expect(result.current.current?.name).toBe("b");
    unmount();
    expect(closes).toEqual(["a", "b"]);
    expect(seen[1]()).toBe(false);
  });
});

describe("useWidget", () => {
  it("mounts once when the node attaches and cleans up when it detaches", () => {
    const cleanups = vi.fn();
    const mount = vi.fn<(root: HTMLDivElement) => () => void>(() => cleanups);
    function Host() {
      const ref = useWidget<HTMLDivElement>(mount);
      return <div ref={ref} />;
    }
    const { rerender, unmount } = render(<Host />);
    rerender(<Host />);
    expect(mount).toHaveBeenCalledTimes(1);
    expect(mount.mock.calls[0][0]).toBeInstanceOf(HTMLDivElement);
    expect(cleanups).not.toHaveBeenCalled();
    unmount();
    expect(cleanups).toHaveBeenCalledTimes(1);
  });
});
