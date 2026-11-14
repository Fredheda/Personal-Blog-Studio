"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../lib/problem";
import { createStudioApi, type Draft, type StudioApi } from "../lib/studio-api";
import { ProblemList } from "./ProblemList";

const STALE = "This post changed elsewhere. Reload it to continue; your unsaved text stays in the box until then.";

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
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState("");
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  function adopt(draft: Draft, parts: { meta?: boolean; body?: boolean } = { meta: true, body: true }) {
    // A save answers with the whole draft, but only the half just saved is
    // adopted: taking the other half's newer ETag would let the next save of
    // that half overwrite a change made in another tab without a 412.
    setSaved((previous) => {
      if (previous === null || (parts.meta && parts.body)) return draft;
      if (parts.meta) {
        return {
          ...previous,
          title: draft.title,
          slug: draft.slug,
          summary: draft.summary,
          tags: draft.tags,
          coverMediaId: draft.coverMediaId,
          updatedAt: draft.updatedAt,
          metaEtag: draft.metaEtag,
        };
      }
      return { ...previous, body: draft.body, bodyEtag: draft.bodyEtag, updatedAt: draft.updatedAt };
    });
    if (parts.meta) {
      setTitle(draft.title);
      setSlug(draft.slug);
      setSummary(draft.summary);
      setTags(draft.tags.join(", "));
    }
    if (parts.body) setBody(draft.body);
  }

  useEffect(() => {
    let alive = true;
    client
      .getPost(id)
      .then((draft) => alive && adopt(draft))
      .catch((e) => alive && setLoadError(e instanceof ApiError ? e : new ApiError(0, null)));
    return () => {
      alive = false;
    };
  }, [client, id, reloadKey]);

  if (loadError) {
    return (
      <section>
        <ProblemList error={loadError} />
        <p><Link href="/">Back to the list</Link></p>
      </section>
    );
  }
  if (saved === null) return <p>Loading…</p>;

  const metaDirty =
    title !== saved.title || slug !== saved.slug || summary !== saved.summary ||
    splitTags(tags).join(",") !== saved.tags.join(",");
  const bodyDirty = body !== saved.body;
  const dirty = metaDirty || bodyDirty;

  async function run(action: () => Promise<void>) {
    setError(null);
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, null));
    }
  }

  const stale = error?.status === 412;
  const shown = stale ? null : error;

  return (
    <section>
      <p><Link href="/">← All posts</Link></p>
      <h1>{saved.title || "(untitled)"}</h1>

      <label htmlFor="title">Title</label>
      <input id="title" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
      <label htmlFor="slug">Slug</label>
      <input id="slug" value={slug} onChange={(e) => setSlug(e.target.value)} />
      <label htmlFor="summary">Summary</label>
      <textarea id="summary" style={{ minHeight: "4rem" }} value={summary} maxLength={500} onChange={(e) => setSummary(e.target.value)} />
      <label htmlFor="tags">Tags (comma separated)</label>
      <input id="tags" value={tags} onChange={(e) => setTags(e.target.value)} />

      <label htmlFor="body">Body (Markdown)</label>
      <textarea id="body" value={body} onChange={(e) => setBody(e.target.value)} />
      <button
        type="button"
        disabled={!dirty}
        onClick={() =>
          run(async () => {
            // One button saves whichever halves have unsaved edits: the details
            // first, then the body, each with its own ETag. Only the half just
            // saved is adopted; a 412 on either half stops here and shows the
            // reload banner (the half already saved stays saved).
            if (metaDirty) {
              const next = await client.patchMeta(id, { title, slug, summary, tags: splitTags(tags) }, saved.metaEtag);
              adopt(next, { meta: true });
            }
            if (bodyDirty) {
              const next = await client.saveBody(id, body, saved.bodyEtag);
              adopt(next, { body: true });
            }
            setNotice("Saved.");
          })
        }
      >
        Save
      </button>

      <hr />
      <button
        type="button"
        disabled={dirty}
        title={dirty ? "Save your edits first" : undefined}
        onClick={() =>
          run(async () => {
            const published = await client.publish(id, saved.bodyEtag);
            setNotice(`Published as version ${published.version}.`);
          })
        }
      >
        Publish
      </button>
      <button
        type="button"
        onClick={() =>
          run(async () => {
            await client.unpublish(id);
            setNotice("Unpublished.");
          })
        }
      >
        Unpublish
      </button>

      {stale && (
        <div role="alert" className="problem">
          {STALE}{" "}
          <button type="button" onClick={() => { setError(null); setReloadKey((k) => k + 1); }}>
            Reload the post
          </button>
        </div>
      )}
      <ProblemList error={shown} />
      {notice && <p className="ok" role="status">{notice}</p>}
    </section>
  );
}
