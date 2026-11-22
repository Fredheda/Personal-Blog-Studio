import type { CheckProblem } from "./studio-api";

/** Spec 7.3, first match wins. */
export type SaveKind = "conflict" | "failed" | "saving" | "details" | "pending" | "saved";
/** Spec 7.5: green filled, white ring, amber ring, red ring, grey ring. */
export type Marker = "done" | "active" | "attention" | "failed" | "waiting";
export type CheckState =
  | { phase: "running" }
  | { phase: "done"; problems: CheckProblem[] }
  | { phase: "failed" };
export type StepView = { marker: Marker; text: string; chip: string };

type SaveInput = {
  conflict: boolean;
  bodyFailed: boolean;
  saving: boolean;
  detailsUnsaved: boolean;
  bodyPending: boolean;
};

export function saveKind(input: SaveInput): SaveKind {
  if (input.conflict) return "conflict";
  if (input.bodyFailed) return "failed";
  if (input.saving) return "saving";
  if (input.detailsUnsaved) return "details";
  if (input.bodyPending) return "pending";
  return "saved";
}

/** Save is enabled where there is something to send (spec 7.3: states 2, 4, 5). */
export function saveEnabled(kind: SaveKind): boolean {
  return kind === "failed" || kind === "details" || kind === "pending";
}

export const SAVE_DOT: Record<SaveKind, string> = {
  conflict: "bg-err",
  failed: "bg-err",
  saving: "bg-muted",
  details: "bg-warn",
  pending: "bg-warn",
  saved: "bg-ok",
};

const SAVE_TEXT: Record<Exclude<SaveKind, "saved">, string> = {
  conflict: "Not saved: the post changed elsewhere",
  failed: "Not saved",
  saving: "Saving…",
  details: "Unsaved details",
  pending: "Unsaved changes",
};

export function saveText(kind: SaveKind, ago: string): string {
  return kind === "saved" ? `Saved ${ago}` : SAVE_TEXT[kind];
}

const MINUTE = 60_000;

/** "just now", "2 min ago", "3 h ago", "2 d ago". A time ahead of `now` counts as now. */
export function relativeTime(from: string, now: number): string {
  const minutes = Math.floor((now - Date.parse(from)) / MINUTE);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.floor(hours / 24)} d ago`;
}

const WRITE: Record<Exclude<SaveKind, "saved">, StepView> = {
  conflict: { marker: "failed", text: "Not saved: the post changed elsewhere.", chip: "Not saved" },
  failed: { marker: "failed", text: "Not saved. Your next edit or Save tries again.", chip: "Not saved" },
  saving: { marker: "active", text: "Saving…", chip: "Saving…" },
  details: { marker: "attention", text: "Unsaved details. Press Save.", chip: "Unsaved details" },
  pending: { marker: "active", text: "Unsaved changes", chip: "Unsaved changes" },
};

export function writeStep(kind: SaveKind, ago: string): StepView {
  return kind === "saved" ? { marker: "done", text: `Saved ${ago}`, chip: "Saved" } : WRITE[kind];
}

export function checkStep(kind: SaveKind, check: CheckState): StepView & { problems: CheckProblem[] } {
  if (kind !== "saved") {
    return { marker: "waiting", text: "Waits for a save", chip: "Waiting", problems: [] };
  }
  if (check.phase === "running") {
    return { marker: "active", text: "Checking…", chip: "Checking…", problems: [] };
  }
  if (check.phase === "failed") {
    return {
      marker: "waiting",
      text: "Could not check. The next save tries again.",
      chip: "Could not check",
      problems: [],
    };
  }
  const n = check.problems.length;
  if (n === 0) return { marker: "done", text: "No problems found", chip: "No problems", problems: [] };
  return {
    marker: "attention",
    text: `${n} thing${n === 1 ? "" : "s"} to fix before publishing`,
    chip: `${n} to fix`,
    problems: check.problems,
  };
}

type PostStatus = { published: boolean; version: number | null; versionPublishedAt: string | null; slug: string };

const day = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

export function publishStep(
  post: PostStatus,
  kind: SaveKind,
  check: CheckState,
): StepView & { canUnpublish: boolean } {
  if (post.published) {
    const on = post.versionPublishedAt ? `, on ${day(post.versionPublishedAt)}` : "";
    return {
      marker: "done",
      text: `Published, version ${post.version}${on}. Publish again to send your changes.`,
      chip: "Published",
      canUnpublish: true,
    };
  }
  const off = (text: string) => ({ marker: "waiting" as const, text, chip: "Not published", canUnpublish: false });
  if (kind !== "saved") return off("Off while something is unsaved");
  if (check.phase === "done" && check.problems.length > 0) return off("Off until the list above is empty");
  if (check.phase === "running") return off("Off until the check is done");
  return {
    marker: "active",
    text: post.slug ? `Not published yet. Goes live at /blog/${post.slug}` : "Not published yet.",
    chip: "Not published",
    canUnpublish: false,
  };
}

/** Spec 7.3: Publish needs a saved post and a check without problems. A failed check does not block: the server validates again. A conflict has no title: the strip's Reload button is the way out. */
export function publishGate(input: { kind: SaveKind; check: CheckState; busy: boolean }): {
  enabled: boolean;
  title?: string;
} {
  if (input.busy || input.kind === "conflict") return { enabled: false };
  if (input.kind !== "saved") return { enabled: false, title: "Save your edits first" };
  if (input.check.phase === "running") return { enabled: false, title: "Checking…" };
  if (input.check.phase === "done" && input.check.problems.length > 0) {
    return { enabled: false, title: "Fix the problems under Check first" };
  }
  return { enabled: true };
}
