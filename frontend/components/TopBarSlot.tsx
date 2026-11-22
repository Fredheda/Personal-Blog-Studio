"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type Slot = { node: HTMLElement | null; setNode: (node: HTMLElement | null) => void };

const SlotContext = createContext<Slot | null>(null);
const NO_SLOT: Slot = { node: null, setNode: () => {} };

/** The right end of the top bar, which a page fills through a portal (spec 7.3: save state and post actions). */
export function TopBarProvider({ children }: { children: ReactNode }) {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const value = useMemo(() => ({ node, setNode }), [node]);
  return <SlotContext.Provider value={value}>{children}</SlotContext.Provider>;
}

export function useTopBarSlot(): Slot {
  return useContext(SlotContext) ?? NO_SLOT;
}
