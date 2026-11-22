"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { createAutosave, type AutosaveStatus } from "../lib/autosave";
import { publishedNotice, unpublishedNotice } from "../lib/live-status";
import { ApiError } from "../lib/problem";
import {
  checkStep,
  publishGate,
  publishStep,
  relativeTime,
  saveEnabled,
  saveKind,
  writeStep,
  type CheckState,
} from "../lib/steps";
import { createStudioApi, type CheckProblem, type Draft, type StudioApi } from "../lib/studio-api";
import { useCheck } from "../lib/use-check";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { MessageStrip } from "./MessageStrip";
import type { EditorHandle } from "./CrepeEditor";
import { PostDetails } from "./PostDetails";
import { Preview } from "./Preview";
import { ProblemList } from "./ProblemList";
import { Sheet } from "./Sheet";
import { Problems, StepChips, StepsLane } from "./StepsLane";
import { TopBarActions } from "./TopBarActions";
import { useTopBarSlot } from "./TopBarSlot";

const CrepeEditor = dynamic(() => import("./CrepeEditor").then((m) => m.CrepeEditor), {
  ssr: false,
  loading: () => <p>Loading the editor…</p>,
});

const STALE = "This post changed elsewhere. Reload it to continue; your unsaved text stays on the page until then.";
const REFUSED = "Not published: fix the problems listed under Check.";

const toApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, null));

export function PostEditor({ id, api }: { id: string; api?: StudioApi }) {
  const client = useMemo(() => api ?? createStudioApi(), [api]);
  const slot = useTopBarSlot();
  const [saved, setSaved] = useState<Draft | null>(null);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [summary, setSummary] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [body, setBody] = useState("");
  const [view, setView] = useState<"edit" | "preview">("edit");
  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const [error, setError] = useState<ApiError | null>(null);
  const [bodyError, setBodyError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [saves, setSaves] = useState(0); // every successful save and every reload: the check asks again
  const [refusal, setRefusal] = useState<{ problems: CheckProblem[]; at: number } | null>(null);
  const [askUnpublish, setAskUnpublish] = useState(false);
  const [sheet, setSheet] = useState<"check" | "publish" | null>(null);
  const [jumpMiss, setJumpMiss] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());

  // The ETags live in refs: the save callback updates the body's before it
  // resolves, so two saves in a row never send a stale one, and the check hook
  // compares its answer with the current pair.
  const bodyEtag = useRef("");
  const metaEtag = useRef("");
  const autosave = useRef<ReturnType<typeof createAutosave> | null>(null);
  const running = useRef(false); // saveAll() in progress: a second click sends nothing
  const editor = useRef<EditorHandle | null>(null);
  const pendingJump = useRef<{ line: number; markdown: string } | null>(null);
  const setEditor = useCallback((handle: EditorHandle | null) => {
    editor.current = handle;
    if (handle === null || pendingJump.current === null) return;
    const { line, markdown } = pendingJump.current;
    pendingJump.current = null;
    setJumpMiss(handle.jumpToLine(line, markdown) ? null : line);
  }, []);

  function adoptLoaded(draft: Draft) {
    setSaved(draft);
    setTitle(draft.title);
    setSlug(draft.slug);
    setSummary(draft.summary);
    setTags(draft.tags);
    setBody(draft.body);
    bodyEtag.current = draft.bodyEtag;
    metaEtag.current = draft.metaEtag;
  }

  // The details were saved: the answer carries the whole draft, but only the
  // details half is adopted. Taking the body's newer ETag would let the next
  // body save overwrite a change made in another tab without a 412. (The body
  // side is updated by the autosave callback itself.)
  function adoptDetails(draft: Draft) {
    setSaved((previous) =>
      previous === null
        ? draft
        : {
            ...previous,
            title: draft.title,
            slug: draft.slug,
            summary: draft.summary,
            tags: draft.tags,
            coverMediaId: draft.coverMediaId,
            updatedAt: draft.updatedAt,
            metaEtag: draft.metaEtag,
          },
    );
    metaEtag.current = draft.metaEtag;
    setTitle(draft.title);
    setSlug(draft.slug);
    setSummary(draft.summary);
    setTags(draft.tags);
  }

  useEffect(() => {
    let alive = true;
    client
      .getPost(id)
      .then((draft) => alive && adoptLoaded(draft))
      .catch((e) => alive && setLoadError(toApiError(e)));
    return () => {
      alive = false;
    };
  }, [client, id, reloadKey]);

  // Display only: keeps "Saved 2 min ago" current. Saving never runs on a timer.
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);

  // One body autosave per loaded post. Leaving flushes first and stops only
  // after the flush settles, so text typed during a save is not lost.
  useEffect(() => {
    // `alive` goes false in the cleanup, before the closing flush runs: that
    // flush still sends the text, but its late answer must not touch the
    // status, the error, the ETag or `saved` of the post that replaced it
    // (after "Reload the post" or a change of post).
    let alive = true;
    const controller = createAutosave({
      delayMs: 1500,
      onStatus: (s) => {
        if (alive) setStatus(s);
      },
      save: async (text) => {
        try {
          const next = await client.saveBody(id, text, bodyEtag.current);
          if (alive) {
            bodyEtag.current = next.bodyEtag; // before this resolves
            setSaved((previous) =>
              previous === null ? previous : { ...previous, body: text, bodyEtag: next.bodyEtag, updatedAt: next.updatedAt },
            );
            setBodyError(null);
            setSaves((n) => n + 1);
          }
        } catch (e) {
          if (alive) setBodyError(toApiError(e)); // the reason must reach the screen
          throw e;
        }
      },
    });
    autosave.current = controller;
    return () => {
      alive = false;
      void controller.close();
    };
  }, [client, id, reloadKey]);

  const check = useCheck({
    api: client,
    id,
    ready: saved !== null,
    saves,
    current: () => ({ bodyEtag: bodyEtag.current, metaEtag: metaEtag.current }),
  });

  const detailsUnsaved =
    saved !== null &&
    (title !== saved.title || slug !== saved.slug || summary !== saved.summary ||
      tags.join(",") !== saved.tags.join(","));

  useEffect(() => {
    const unsaved =
      detailsUnsaved || status === "pending" || status === "saving" || status === "error" || status === "conflict";
    if (!unsaved) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [status, detailsUnsaved]);

  if (loadError) {
    return (
      <section className="mx-auto max-w-[720px] px-6 pt-10">
        <ProblemList error={loadError} />
        <p><Link href="/">Back to the list</Link></p>
      </section>
    );
  }
  if (saved === null) return <p className="px-6 pt-10">Loading…</p>;

  const metaDirty = detailsUnsaved;
  const bodyUnsaved = status === "pending" || status === "saving" || status === "error";
  const conflict = status === "conflict" || error?.status === 412 || bodyError?.status === 412;
  const kind = saveKind({
    conflict,
    bodyFailed: status === "error",
    saving: busy || status === "saving",
    detailsUnsaved: metaDirty,
    bodyPending: status === "pending",
  });
  const ago = relativeTime(saved.updatedAt, now);
  const activeRefusal = refusal !== null && refusal.at === saves ? refusal.problems : null;
  const checkState: CheckState = activeRefusal ? { phase: "done", problems: activeRefusal } : check;
  const gate = publishGate({ kind, check: checkState, busy: busy || publishing });
  const writeView = writeStep(kind, ago);
  const checkView = checkStep(kind, checkState);
  const publishView = publishStep(saved, kind, checkState);

  /** Saves everything that is unsaved: the details first (details ETag), then
   *  the body (body ETag, through the autosave controller). True only when both
   *  halves are saved. A details failure is shown, but the body is still
   *  flushed so typed text is stored before the owner reloads. */
  async function saveAll(): Promise<boolean> {
    if (running.current) return false;
    running.current = true;
    setBusy(true);
    setNotice("");
    let ok = true;
    try {
      if (metaDirty) {
        try {
          const next = await client.patchMeta(id, { title, slug, summary, tags }, saved!.metaEtag);
          adoptDetails(next);
          setError(null);
          setSaves((n) => n + 1);
        } catch (e) {
          setError(toApiError(e));
          ok = false;
        }
      }
      const bodySaved = (await autosave.current?.flush()) ?? true;
      if (!bodySaved) ok = false;
    } finally {
      running.current = false;
      setBusy(false);
    }
    return ok;
  }

  /** The status fields (published, version, dates) of the post as the API has them now; never the text. */
  async function refreshStatus() {
    try {
      const fresh = await client.getPost(id);
      setSaved((previous) =>
        previous === null
          ? previous
          : {
              ...previous,
              published: fresh.published,
              version: fresh.version,
              publishedAt: fresh.publishedAt,
              versionPublishedAt: fresh.versionPublishedAt,
              slugLocked: fresh.slugLocked,
            },
      );
    } catch (e) {
      setError(toApiError(e));
    }
  }

  async function doPublish() {
    setPublishing(true);
    setError(null);
    setNotice("");
    setRefusal(null);
    try {
      const published = await client.publish(id, bodyEtag.current);
      setNotice(publishedNotice(published.version, published.slug));
      await refreshStatus();
    } catch (e) {
      const failure = toApiError(e);
      const listed = failure.problem?.problems ?? [];
      if (failure.status === 422 && listed.length > 0) setRefusal({ problems: listed, at: saves });
      else setError(failure);
    } finally {
      setPublishing(false);
    }
  }

  async function doUnpublish() {
    setAskUnpublish(false);
    setError(null);
    setNotice("");
    try {
      await client.unpublish(id);
      setNotice(unpublishedNotice(saved!.slug));
      await refreshStatus();
    } catch (e) {
      setError(toApiError(e));
    }
  }

  const shownError = error?.status === 412 ? null : error;
  const shownBodyError = bodyError?.status === 412 ? null : bodyError;
  const edited = () => {
    setNotice("");
    setJumpMiss(null);
  };

  function jumpTo(line: number) {
    setSheet(null);
    setView("edit");
    const markdown = saved!.body;
    requestAnimationFrame(() => {
      if (editor.current === null) {
        pendingJump.current = { line, markdown };
        return;
      }
      setJumpMiss(editor.current.jumpToLine(line, markdown) ? null : line);
    });
  }

  return (
    <div className="min-[760px]:grid min-[760px]:grid-cols-[232px_1fr] min-[1180px]:grid-cols-[262px_1fr]">
      <StepChips
        write={writeView}
        check={checkView}
        publish={publishView}
        onOpenProblems={() => setSheet("check")}
        onOpenPublish={() => setSheet("publish")}
      />
      <aside
        aria-label="Post steps"
        className="hidden border-line bg-deep p-4 min-[760px]:block min-[760px]:min-h-[calc(100vh-58px)] min-[760px]:border-r"
      >
        <div className="min-[760px]:sticky min-[760px]:top-[58px] min-[760px]:max-h-[calc(100vh-58px)] min-[760px]:overflow-y-auto">
          <StepsLane
            write={writeView}
            check={checkView}
            publish={publishView}
            onUnpublish={() => setAskUnpublish(true)}
            onJump={jumpTo}
          />
        </div>
      </aside>

      <section className="mx-auto w-full min-w-0 max-w-[720px] px-[18px] pb-24 pt-6 min-[760px]:px-6 min-[760px]:pb-10 min-[760px]:pt-10">
        {conflict && (
          <MessageStrip
            kind="conflict"
            action={
              <Button
                variant="primary"
                className="m-0"
                onClick={() => {
                  setError(null);
                  setBodyError(null);
                  setRefusal(null);
                  setStatus("idle");
                  setSaved(null); // the editor remounts with the reloaded text
                  setSaves((n) => n + 1);
                  setReloadKey((k) => k + 1);
                }}
              >
                Reload the post
              </Button>
            }
          >
            {STALE}
          </MessageStrip>
        )}
        <ProblemList error={shownBodyError} />
        <ProblemList error={shownError} />
        {activeRefusal && <MessageStrip kind="warning">{REFUSED}</MessageStrip>}
        {notice && <MessageStrip kind="success">{notice}</MessageStrip>}
        {jumpMiss !== null && <MessageStrip kind="error">Could not find line {jumpMiss} in the editor.</MessageStrip>}

        <PostDetails
          title={title}
          summary={summary}
          slug={slug}
          tags={tags}
          slugLocked={saved.slugLocked}
          preview={view === "preview"}
          onTitle={(value) => { setTitle(value); edited(); }}
          onSummary={(value) => { setSummary(value); edited(); }}
          onSlug={(value) => { setSlug(value); edited(); }}
          onTags={(value) => { setTags(value); edited(); }}
        />

        <div className="mt-4" hidden={view !== "edit"}>
          <CrepeEditor
            key={reloadKey}
            onReady={setEditor}
            initial={saved.body}
            onChange={(text) => {
              setBody(text);
              edited();
              autosave.current?.push(text);
            }}
          />
        </div>
        {view === "preview" && (
          <div className="mt-4">
            {bodyUnsaved && <p className="status">Preview of the text as you typed it.</p>}
            <Preview markdown={body} />
          </div>
        )}
      </section>

      {slot.node &&
        createPortal(
          <TopBarActions
            kind={kind}
            ago={ago}
            previewOn={view === "preview"}
            onPreview={() => setView((v) => (v === "edit" ? "preview" : "edit"))}
            canSave={saveEnabled(kind)}
            onSave={() => void saveAll()}
            publish={gate}
            onPublish={() => void doPublish()}
          />,
          slot.node,
        )}

      {askUnpublish && (
        <Dialog
          title="Unpublish this post?"
          cancelLabel="Keep it published"
          confirmLabel="Unpublish"
          onCancel={() => setAskUnpublish(false)}
          onConfirm={() => void doUnpublish()}
        >
          It leaves the blog at once. The draft and its published versions stay in the studio.
        </Dialog>
      )}
      {sheet === "check" && (
        <Sheet title="Check" onClose={() => setSheet(null)}>
          <p className="m-0 text-muted">{checkView.text}</p>
          <Problems problems={checkView.problems} onJump={jumpTo} />
        </Sheet>
      )}
      {sheet === "publish" && (
        <Sheet title="Publish" onClose={() => setSheet(null)}>
          <p className="m-0 text-muted">{publishView.text}</p>
          {publishView.canUnpublish && (
            <Button
              className="mt-3"
              onClick={() => {
                setSheet(null);
                setAskUnpublish(true);
              }}
            >
              Unpublish
            </Button>
          )}
        </Sheet>
      )}
    </div>
  );
}
