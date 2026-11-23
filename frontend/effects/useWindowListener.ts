import { useEffect } from "react";

import { useLatest } from "./useLatest";

export function useWindowListener<K extends keyof WindowEventMap>(
  type: K,
  handler: (event: WindowEventMap[K]) => void,
  enabled = true,
) {
  const latest = useLatest(handler);
  useEffect(() => {
    if (!enabled) return;
    const listener = (event: WindowEventMap[K]) => latest.current(event);
    window.addEventListener(type, listener);
    return () => window.removeEventListener(type, listener);
  }, [type, enabled, latest]);
}
