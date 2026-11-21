import type { ReactNode } from "react";

/** A status pill (spec 7.8): a grey ring for a draft, a green dot for a published post. */
export function Pill({ tone, children }: { tone: "draft" | "published"; children: ReactNode }) {
  const mark = tone === "published" ? "bg-ok" : "border-[1.5px] border-muted";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-pane px-2.5 py-0.5 text-[12.5px] text-muted">
      <span aria-hidden className={`size-2 rounded-full ${mark}`} />
      {children}
    </span>
  );
}
