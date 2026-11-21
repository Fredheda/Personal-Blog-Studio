"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { createAutosave, type AutosaveStatus } from "../lib/autosave";
import { publishedNotice, unpublishedNotice } from "../lib/live-status";
import { ApiError } from "../lib/problem";
import { createStudioApi, type Draft, type StudioApi } from "../lib/studio-api";
import { Button } from "./Button";
import { MessageStrip } from "./MessageStrip";
import { Preview } from "./Preview";
import { ProblemList } from "./ProblemList";

const CrepeEditor = dynamic(() => import("./CrepeEditor").then((m) => m.CrepeEditor), {
  ssr: false,
  loading: () => <p>Loading the editor…</p>,
});

const STALE = "This post changed elsewhere. Reload it to continue; your unsaved text stays on the page until then.";
const STATUS_TEXT: Record<AutosaveStatus, string> = {
  idle: "",
  pending: "Unsaved changes",
  saving: "Saving…",
  saved: "Saved",
  conflict: "Not saved",
  error: "Not saved (press Save or keep typing to try again)",
};

const toApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, null));

function splitTags(text: string): string[] {
  return text.split(",").map((t) => t.trim()).filter((t) => t !== "");
}

export function PostEditor({ id, api }: { id: string; api?: StudioApi }) {
  const client = useMemo(() => api ?? createStudioApi(), [api]);
  const [saved, setSaved] = useState<Draft | null>(null);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [summary, setSummary] = useState("");
  const [tags, setTags] = useState("");
  const [body, setBody] = useState("");
  const [view, setView] = useState<"edit" | "preview">("edit");
  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const [error, setError] = useState<ApiError | null>(null); // details, publish, unpublish
  const [bodyError, setBodyError] = useState<ApiError | null>(null); // autosave
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // The body ETag lives in a ref: the save callback updates it before it
  // resolves, so two saves in a row never send a stale one.
  const bodyEtag = useRef("");
  const autosave = useRef<ReturnType<typeof createAutosave> | null>(null);
  const running = useRef(false); // saveAll() in progress: a second click sends nothing

  // A freshly loaded post: every field and both ETags.
  function adoptLoaded(draft: Draft) {
    setSaved(draft);
    setTitle(draft.title);
    setSlug(draft.slug);
    setSummary(draft.summary);
    setTags(draft.tags.join(", "));
    setBody(draft.body);
    bodyEtag.current = draft.bodyEtag;
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
    setTitle(draft.title);
    setSlug(draft.slug);
    setSummary(draft.summary);
    setTags(draft.tags.join(", "));
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

  // Unsaved details count too: leaving with an edited title or slug warns.
  const detailsUnsaved =
    saved !== null &&
    (title !== saved.title || slug !== saved.slug || summary !== saved.summary ||
      splitTags(tags).join(",") !== saved.tags.join(","));

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
      <section>
        <ProblemList error={loadError} />
        <p><Link href="/">Back to the list</Link></p>
      </section>
    );
  }
  if (saved === null) return <p>Loading…</p>;

  const metaDirty = detailsUnsaved;
  const bodyUnsaved = status === "pending" || status === "saving" || status === "error";
  const conflict = status === "conflict" || error?.status === 412 || bodyError?.status === 412;

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
          const next = await client.patchMeta(id, { title, slug, summary, tags: splitTags(tags) }, saved!.metaEtag);
          adoptDetails(next);
          setError(null);
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
    if (ok) setNotice("Saved.");
    return ok;
  }

  async function run(action: () => Promise<void>) {
    setError(null);
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(toApiError(e));
    }
  }

  const shownError = error?.status === 412 ? null : error;
  const shownBodyError = bodyError?.status === 412 ? null : bodyError;

  return (
    <section>
      <h1>{saved.title || "(untitled)"}</h1>

      <label htmlFor="title">Title</label>
      <input id="title" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
      <label htmlFor="slug">Slug</label>
      <input id="slug" value={slug} onChange={(e) => setSlug(e.target.value)} />
      <label htmlFor="summary">Summary</label>
      <textarea id="summary" style={{ minHeight: "4rem" }} value={summary} maxLength={500} onChange={(e) => setSummary(e.target.value)} />
      <label htmlFor="tags">Tags (comma separated, optional)</label>
      <input id="tags" value={tags} onChange={(e) => setTags(e.target.value)} />

      <div className="tabs" role="group" aria-label="View">
        <Button aria-pressed={view === "edit"} onClick={() => setView("edit")}>Edit</Button>
        <Button aria-pressed={view === "preview"} onClick={() => setView("preview")}>Preview</Button>
      </div>
      <div hidden={view !== "edit"}>
        <CrepeEditor
          key={reloadKey}
          initial={saved.body}
          onChange={(text) => {
            setBody(text);
            autosave.current?.push(text);
          }}
        />
      </div>
      {view === "preview" && (
        <>
          {bodyUnsaved && <p className="status">Preview of the text as you typed it.</p>}
          <Preview markdown={body} />
        </>
      )}
      <p className="status" role="status">{STATUS_TEXT[status]}</p>

      <Button
        disabled={busy || conflict || (!metaDirty && !bodyUnsaved)}
        onClick={() => void saveAll()}
      >
        Save
      </Button>

      <hr />
      <Button
        variant="primary"
        disabled={busy || conflict || metaDirty || bodyUnsaved}
        title={metaDirty || bodyUnsaved ? "Save your edits first" : undefined}
        onClick={() =>
          run(async () => {
            const published = await client.publish(id, bodyEtag.current);
            setNotice(publishedNotice(published.version, published.slug));
          })
        }
      >
        Publish
      </Button>
      <Button
        onClick={() =>
          run(async () => {
            await client.unpublish(id);
            setNotice(unpublishedNotice(saved.slug));
          })
        }
      >
        Unpublish
      </Button>

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
                setStatus("idle");
                setSaved(null); // the editor remounts with the reloaded text
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
      {notice && <MessageStrip kind="success">{notice}</MessageStrip>}
    </section>
  );
}
