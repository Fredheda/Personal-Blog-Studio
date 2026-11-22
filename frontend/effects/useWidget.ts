import { useCallback, type RefCallback } from "react";

import { useLatest } from "./useLatest";

export function useWidget<E extends HTMLElement>(
  mount: (root: E) => () => void,
): RefCallback<E> {
  const latest = useLatest(mount);
  return useCallback((node: E | null) => (node ? latest.current(node) : undefined), [latest]);
}
