import type { ReactNode } from "react";

const KIND = {
  conflict: {
    role: "alert",
    look: "border-warn bg-[color-mix(in_srgb,var(--color-warn)_12%,var(--color-pane))]",
  },
  error: {
    role: "alert",
    look: "border-err bg-[color-mix(in_srgb,var(--color-err)_12%,var(--color-pane))]",
  },
  success: {
    role: "status",
    look: "border-ok bg-[color-mix(in_srgb,var(--color-ok)_12%,var(--color-pane))]",
  },
} as const;

/** One message strip (spec 7.7): amber for a conflict, red for a failure, green for what just happened. */
export function MessageStrip({
  kind,
  children,
  action,
}: {
  kind: keyof typeof KIND;
  children: ReactNode;
  action?: ReactNode;
}) {
  const { role, look } = KIND[kind];
  return (
    <div role={role} className={`my-3 flex flex-wrap items-center gap-x-3 rounded-xl border px-3 py-2 ${look}`}>
      <div className="min-w-0 flex-1">{children}</div>
      {action}
    </div>
  );
}
