"use client";

import { useState } from "react";

import { slugInput } from "../lib/slug";
import { addTags, removeLast, removeTag } from "../lib/tags";

type Props = {
  title: string;
  summary: string;
  slug: string;
  tags: string[];
  slugLocked: boolean;
  preview: boolean;
  onTitle: (value: string) => void;
  onSummary: (value: string) => void;
  onSlug: (value: string) => void;
  onTags: (value: string[]) => void;
};

const PILL =
  "inline-flex items-center gap-1.5 rounded-full border border-line bg-pane px-2.5 py-0.5 text-[12.5px] text-muted";
const DASHED =
  "inline-flex items-center rounded-full border border-dashed border-line bg-transparent px-2.5 py-0.5 text-[12.5px] text-muted";

function Lock() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-3" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="7" width="10" height="7" rx="1.5" />
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" />
    </svg>
  );
}

export function PostDetails({
  title,
  summary,
  slug,
  tags,
  slugLocked,
  preview,
  onTitle,
  onSummary,
  onSlug,
  onTags,
}: Props) {
  const [editingSlug, setEditingSlug] = useState(false);
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");

  if (preview) {
    return (
      <div>
        <h1>{title || "(untitled)"}</h1>
        {summary && <p className="text-[18.5px] text-muted">{summary}</p>}
        <div className="mt-3 flex flex-wrap items-center gap-2 border-b border-line pb-4">
          {slug && <span className={PILL}>/{slug}</span>}
          {tags.map((tag) => (
            <span key={tag} className={PILL}>
              {tag}
            </span>
          ))}
        </div>
      </div>
    );
  }

  function addText(value: string) {
    const next = addTags(tags, value);
    if (next.length !== tags.length) onTags(next);
    setText("");
  }

  return (
    <div>
      <h1>
        <input
          aria-label="Title"
          placeholder="Title"
          maxLength={200}
          value={title}
          onChange={(e) => onTitle(e.target.value)}
          className="w-full border-0 bg-transparent p-0 text-[inherit] font-[inherit] text-text outline-none placeholder:text-muted"
        />
      </h1>
      <textarea
        aria-label="Summary"
        placeholder="Add a summary: one or two sentences for lists and previews"
        maxLength={500}
        rows={2}
        value={summary}
        onChange={(e) => onSummary(e.target.value)}
        className="mt-1 w-full resize-none field-sizing-content border-0 bg-transparent p-0 text-[18.5px] text-muted outline-none placeholder:text-muted"
      />
      <div className="mt-3 flex flex-wrap items-center gap-2 border-b border-line pb-4">
        {slugLocked ? (
          <span className={PILL} title="The slug is fixed once the post has been published">
            <Lock />
            {slug ? `/${slug}` : "No slug"}
          </span>
        ) : editingSlug ? (
          <input
            aria-label="Slug"
            autoFocus
            maxLength={100}
            value={slug}
            onChange={(e) => onSlug(slugInput(e.target.value))}
            onBlur={() => setEditingSlug(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === "Escape") setEditingSlug(false);
            }}
            className={`${PILL} w-48 outline-none`}
          />
        ) : (
          <button type="button" className={slug ? PILL : DASHED} onClick={() => setEditingSlug(true)}>
            {slug ? `/${slug}` : "Add a slug"}
          </button>
        )}
        {tags.map((tag) => (
          <span key={tag} className={PILL}>
            {tag}
            <button type="button" aria-label={`Remove tag ${tag}`} onClick={() => onTags(removeTag(tags, tag))}>
              ×
            </button>
          </span>
        ))}
        {adding ? (
          <input
            aria-label="Tags"
            autoFocus
            value={text}
            onChange={(e) => {
              const value = e.target.value;
              if (value.includes(",")) {
                addText(value);
              } else {
                setText(value);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addText(text);
              } else if (e.key === "Backspace" && text === "" && tags.length > 0) {
                onTags(removeLast(tags));
              }
            }}
            onBlur={() => {
              addText(text);
              setAdding(false);
            }}
            className={`${PILL} w-32 outline-none`}
          />
        ) : (
          <button type="button" className={DASHED} onClick={() => setAdding(true)}>
            Add a tag
          </button>
        )}
      </div>
    </div>
  );
}
