import { useEffect } from "react";

import { useLatest } from "./useLatest";

export function useInterval(fn: () => void, ms: number | null) {
  const latest = useLatest(fn);
  useEffect(() => {
    if (ms === null) return;
    const timer = setInterval(() => latest.current(), ms);
    return () => clearInterval(timer);
  }, [ms, latest]);
}
