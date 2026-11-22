"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useTopBarSlot } from "./TopBarSlot";

/** The 58px bar of every page (spec 7.3): the brand and "All posts"; it stays
 *  in view on a long page. The save state and the post actions come through
 *  the slot at its right. */
export function TopBar() {
  const pathname = usePathname();
  const { setNode } = useTopBarSlot();
  return (
    <header className="sticky top-0 z-30 flex h-[58px] items-center gap-6 border-b border-line bg-bg px-5">
      <Link href="/" className="flex items-center gap-2 font-semibold text-text no-underline">
        <span aria-hidden className="brand-dot size-3 rounded-full" />
        Studio
      </Link>
      <nav aria-label="Main">
        <Link
          href="/"
          aria-current={pathname === "/" ? "page" : undefined}
          className="rounded-lg px-3 py-1.5 text-muted no-underline aria-[current=page]:bg-pane aria-[current=page]:text-text"
        >
          All posts
        </Link>
      </nav>
      <div ref={setNode} className="ml-auto flex items-center" />
    </header>
  );
}
