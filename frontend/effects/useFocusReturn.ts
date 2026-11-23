import { useEffect, type RefObject } from "react";

export function useFocusReturn(target: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    target.current?.focus();
    return () => before?.focus();
  }, [target]);
}
