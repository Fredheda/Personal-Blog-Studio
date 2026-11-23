import { useEffect } from "react";

import { useLatest } from "./useLatest";

type Callbacks<T> = {
  onResult: (value: T) => void;
  onError?: (error: unknown) => void;
  enabled?: boolean;
};

export function useRequest<T>(
  request: () => Promise<T>,
  key: unknown,
  { onResult, onError, enabled = true }: Callbacks<T>,
) {
  const latest = useLatest({ request, onResult, onError });
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    latest.current
      .request()
      .then((value) => {
        if (alive) latest.current.onResult(value);
      })
      .catch((error: unknown) => {
        if (alive) latest.current.onError?.(error);
      });
    return () => {
      alive = false;
    };
  }, [enabled, key, latest]);
}
