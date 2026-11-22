import { useEffect, useRef, type RefObject } from "react";

import { useLatest } from "./useLatest";

export function useController<T extends { close: () => unknown }>(
  create: (alive: () => boolean) => T,
  key: unknown,
): RefObject<T | null> {
  const controller = useRef<T | null>(null);
  const latest = useLatest(create);
  useEffect(() => {
    let alive = true;
    const created = latest.current(() => alive);
    controller.current = created;
    return () => {
      alive = false;
      void created.close();
    };
  }, [key, latest]);
  return controller;
}
