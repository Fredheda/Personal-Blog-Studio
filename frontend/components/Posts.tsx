"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../lib/problem";
import { createStudioApi, type ListItem, type StudioApi } from "../lib/studio-api";
import { ProblemList } from "./ProblemList";

export function Posts({ api }: { api?: StudioApi }) {
  const client = useMemo(() => api ?? createStudioApi(), [api]);
  const router = useRouter();
  const [items, setItems] = useState<ListItem[] | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let alive = true;
    client
      .listPosts()
      .then((list) => alive && setItems(list))
      .catch((e) => alive && setLoadError(e instanceof ApiError ? e : new ApiError(0, null)));
    return () => {
      alive = false;
    };
  }, [client]);

  async function create() {
    setError(null);
    try {
      const draft = await client.createPost(title.trim());
      router.push(`/posts/${draft.postId}`);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, null));
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
        <button type="submit" disabled={title.trim() === ""}>Create post</button>
      </form>
      <ProblemList error={error} />
      <ProblemList error={loadError} />
      {items !== null && items.length === 0 && <p>No posts yet.</p>}
      {items !== null && items.length > 0 && (
        <ul className="posts">
          {items.map((post) => (
            <li key={post.postId}>
              <Link href={`/posts/${post.postId}`}>{post.title || "(untitled)"}</Link>
              <span className="muted">{post.slug ? ` /${post.slug}` : ""} · {post.updatedAt}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
