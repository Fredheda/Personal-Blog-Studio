import { act, cleanup, render, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useController } from "./useController";
import { useFocusReturn } from "./useFocusReturn";
import { useInterval } from "./useInterval";
import { useLatest } from "./useLatest";
import { useRequest } from "./useRequest";
import { useWidget } from "./useWidget";
import { useWindowListener } from "./useWindowListener";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("useLatest", () => {
  it("holds the value of the latest render", () => {
    const { result, rerender } = renderHook(({ value }) => useLatest(value), {
      initialProps: { value: 1 },
    });
    expect(result.current.current).toBe(1);
    rerender({ value: 2 });
    expect(result.current.current).toBe(2);
  });
});

describe("useWindowListener", () => {
  it("calls the latest handler while enabled and stops when disabled", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(
      ({ handler, enabled }) => useWindowListener("beforeunload", handler, enabled),
      { initialProps: { handler: first, enabled: true } },
    );
    rerender({ handler: second, enabled: true });
    window.dispatchEvent(new Event("beforeunload"));
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
    rerender({ handler: second, enabled: false });
    window.dispatchEvent(new Event("beforeunload"));
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("removes the listener on unmount", () => {
    const handler = vi.fn();
    const { unmount } = renderHook(() => useWindowListener("beforeunload", handler));
    unmount();
    window.dispatchEvent(new Event("beforeunload"));
    expect(handler).not.toHaveBeenCalled();
  });
});

describe("useInterval", () => {
  it("runs the latest function on every tick, pauses on null and stops on unmount", () => {
    vi.useFakeTimers();
    const first = vi.fn();
    const second = vi.fn();
    const { rerender, unmount } = renderHook(({ fn, ms }) => useInterval(fn, ms), {
      initialProps: { fn: first, ms: 1000 as number | null },
    });
    rerender({ fn: second, ms: 1000 });
    vi.advanceTimersByTime(2000);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(2);
    rerender({ fn: second, ms: null });
    vi.advanceTimersByTime(5000);
    expect(second).toHaveBeenCalledTimes(2);
    rerender({ fn: second, ms: 1000 });
    unmount();
    vi.advanceTimersByTime(5000);
    expect(second).toHaveBeenCalledTimes(2);
  });
});

describe("useRequest", () => {
  function deferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (error: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  }

  it("hands the result to the latest callback", async () => {
    const onResult = vi.fn();
    const { rerender } = renderHook(
      ({ cb }) => useRequest(() => Promise.resolve("a"), "k", { onResult: cb }),
      { initialProps: { cb: vi.fn() } },
    );
    rerender({ cb: onResult });
    await act(async () => {});
    expect(onResult).toHaveBeenCalledWith("a");
  });

  it("drops the answer of a request whose key has changed", async () => {
    const slow = deferred<string>();
    const onResult = vi.fn();
    const { rerender } = renderHook(
      ({ key }) =>
        useRequest(() => (key === "old" ? slow.promise : Promise.resolve("new")), key, {
          onResult,
        }),
      { initialProps: { key: "old" } },
    );
    rerender({ key: "new" });
    await act(async () => {});
    slow.resolve("stale");
    await act(async () => {});
    expect(onResult.mock.calls).toEqual([["new"]]);
  });

  it("drops the answer of a request whose owner unmounted", async () => {
    const slow = deferred<string>();
    const onResult = vi.fn();
    const { unmount } = renderHook(() => useRequest(() => slow.promise, "k", { onResult }));
    unmount();
    slow.resolve("late");
    await act(async () => {});
    expect(onResult).not.toHaveBeenCalled();
  });

  it("does not report a late failure of a request whose key has changed", async () => {
    const slow = deferred<string>();
    const onError = vi.fn();
    const { rerender } = renderHook(
      ({ key }) =>
        useRequest(() => (key === "old" ? slow.promise : Promise.resolve("new")), key, {
          onResult: vi.fn(),
          onError,
        }),
      { initialProps: { key: "old" } },
    );
    rerender({ key: "new" });
    await act(async () => {});
    slow.reject(new Error("late"));
    await act(async () => {});
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports an error only while the request is current and skips a disabled one", async () => {
    const onError = vi.fn();
    const request = vi.fn(() => Promise.reject(new Error("no")));
    const { rerender } = renderHook(
      ({ enabled }) => useRequest(request, "k", { onResult: vi.fn(), onError, enabled }),
      { initialProps: { enabled: false } },
    );
    await act(async () => {});
    expect(request).not.toHaveBeenCalled();
    rerender({ enabled: true });
    await act(async () => {});
    expect(onError).toHaveBeenCalledTimes(1);
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

describe("useFocusReturn", () => {
  it("focuses the target and gives the focus back on unmount", () => {
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();
    function Panel() {
      const target = { current: null as HTMLButtonElement | null };
      const ref = (node: HTMLButtonElement | null) => {
        target.current = node;
      };
      useFocusReturn(target);
      return <button ref={ref}>ok</button>;
    }
    const { unmount, getByText } = render(<Panel />);
    expect(document.activeElement).toBe(getByText("ok"));
    unmount();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });
});
