"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { useRequest } from "../effects/useRequest";
import { postStatus } from "../lib/live-status";
import { ApiError } from "../lib/problem";
import { createStudioApi, isConfirmationRequired, type ListItem, type StudioApi } from "../lib/studio-api";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { Pill } from "./Pill";
import { ProblemList } from "./ProblemList";

export function Posts({ api }: { api?: StudioApi }) {
  const client = useMemo(() => api ?? createStudioApi(), [api]);
  const router = useRouter();
  const [items, setItems] = useState<ListItem[] | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [ask, setAsk] = useState<{ post: ListItem; kind: "draft" | "post" } | null>(null);

  useRequest(() => client.listPosts(), client, {
    onResult: setItems,
    onError: (e) => setLoadError(e instanceof ApiError ? e : new ApiError(0, null)),
  });

  async function create() {
    setError(null);
    try {
      const draft = await client.createPost(title.trim());
      router.push(`/posts/${draft.postId}`);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, null));
    }
  }

  function startDelete(post: ListItem) {
    setError(null);
    setAsk({ post, kind: post.published ? "post" : "draft" });
  }

  async function confirmDelete({ post, kind }: { post: ListItem; kind: "draft" | "post" }) {
    setAsk(null);
    setBusyId(post.postId);
    const drop = () => setItems((list) => list && list.filter((p) => p.postId !== post.postId));
    try {
      if (kind === "post") {
        await client.deletePost(post.postId, { confirm: "published" });
      } else {
        try {
          await client.deletePost(post.postId);
        } catch (e) {
          if (!isConfirmationRequired(e)) throw e;
          setAsk({ post, kind: "post" }); // it was published once: ask again, in the post's words
          return;
        }
      }
      drop();
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) drop(); // already gone, for example a retry after a timeout
      else setError(e instanceof ApiError ? e : new ApiError(0, null));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void create();
        }}
      >
        <label>
          Title
          <input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <Button type="submit" variant="primary" disabled={title.trim() === ""}>Create post</Button>
      </form>
      <ProblemList error={error} />
      <ProblemList error={loadError} />
      {items !== null && items.length === 0 && <p>No posts yet.</p>}
      {items !== null && items.length > 0 && (
        <ul className="posts">
          {items.map((post) => (
            <li key={post.postId}>
              <Link href={`/posts/${post.postId}`}>{post.title || "(untitled)"}</Link>
              <span className="muted">{post.slug ? ` /${post.slug} · ` : " "}</span>
              <Pill tone={post.published ? "published" : "draft"}>{postStatus(post)}</Pill>
              <span className="muted"> · {post.updatedAt}</span>
              <Button
                aria-label={`Delete ${post.title || "(untitled)"}`}
                disabled={busyId === post.postId}
                onClick={() => startDelete(post)}
              >
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}
      {ask && (
        <Dialog
          title={ask.kind === "draft" ? "Delete this draft?" : "Delete this post?"}
          cancelLabel="Keep it"
          confirmLabel={ask.kind === "draft" ? "Delete draft" : "Delete post"}
          onCancel={() => setAsk(null)}
          onConfirm={() => void confirmDelete(ask)}
        >
          {ask.kind === "draft"
            ? `"${ask.post.title || "(untitled)"}" and its revisions are removed. You can get it back for 7 days by asking.`
            : `"${ask.post.title || "(untitled)"}" is taken off the blog and removed, with its published versions. You can get it back for 7 days by asking.`}
        </Dialog>
      )}
    </section>
  );
}
