import { useEffect } from "react";

import { useLatest } from "./useLatest";

export function useInterval(fn: () => void, ms: number) {
  const latest = useLatest(fn);
  useEffect(() => {
    const timer = setInterval(() => latest.current(), ms);
    return () => clearInterval(timer);
  }, [ms, latest]);
}
