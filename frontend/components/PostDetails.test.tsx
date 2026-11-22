import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PostDetails } from "./PostDetails";

afterEach(cleanup);

function Harness({
  slugLocked = false,
  preview = false,
  initial = { title: "Hello", summary: "Sum", slug: "hello", tags: ["maths"] },
}: {
  slugLocked?: boolean;
  preview?: boolean;
  initial?: { title: string; summary: string; slug: string; tags: string[] };
}) {
  const [title, setTitle] = useState(initial.title);
  const [summary, setSummary] = useState(initial.summary);
  const [slug, setSlug] = useState(initial.slug);
  const [tags, setTags] = useState(initial.tags);
  return (
    <PostDetails
      title={title}
      summary={summary}
      slug={slug}
      tags={tags}
      slugLocked={slugLocked}
      preview={preview}
      onTitle={setTitle}
      onSummary={setSummary}
      onSlug={setSlug}
      onTags={setTags}
    />
  );
}

describe("title and summary", () => {
  it("are typed in place with their names, limits and placeholders", () => {
    render(<Harness initial={{ title: "", summary: "", slug: "", tags: [] }} />);
    const title = screen.getByLabelText("Title") as HTMLInputElement;
    expect(title.placeholder).toBe("Title");
    expect(title.maxLength).toBe(200);
    expect(title.closest("h1")).not.toBeNull();
    const summary = screen.getByLabelText("Summary") as HTMLTextAreaElement;
    expect(summary.placeholder).toBe("Add a summary: one or two sentences for lists and previews");
    expect(summary.maxLength).toBe(500);
    fireEvent.change(title, { target: { value: "New" } });
    fireEvent.change(summary, { target: { value: "Words" } });
    expect(title.value).toBe("New");
    expect(summary.value).toBe("Words");
  });
});

describe("the slug pill", () => {
  it("shows the slug, turns into an input on a click and closes on Enter", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "/hello" }));
    const input = screen.getByLabelText("Slug") as HTMLInputElement;
    expect(document.activeElement).toBe(input);
    fireEvent.change(input, { target: { value: "hello-2" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.queryByLabelText("Slug")).toBeNull();
    expect(screen.getByRole("button", { name: "/hello-2" })).toBeTruthy();
  });

  it("accepts only lower-case letters, digits and hyphens, up to 100", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "/hello" }));
    const input = screen.getByLabelText("Slug") as HTMLInputElement;
    expect(input.maxLength).toBe(100);
    fireEvent.change(input, { target: { value: "Hello World!" } });
    expect(input.value).toBe("hello-world");
  });

  it("shows a dashed add button when empty", () => {
    render(<Harness initial={{ title: "T", summary: "", slug: "", tags: [] }} />);
    expect(screen.getByRole("button", { name: "Add a slug" })).toBeTruthy();
  });

  it("is read only with a lock once the post has been published", () => {
    render(<Harness slugLocked />);
    expect(screen.queryByRole("button", { name: "/hello" })).toBeNull();
    const pill = screen.getByTitle("The slug is fixed once the post has been published");
    expect(pill.textContent).toContain("/hello");
  });
});

describe("the tag pills", () => {
  it("lists the tags with a remove button each", () => {
    render(<Harness initial={{ title: "T", summary: "", slug: "s", tags: ["a", "b"] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove tag a" }));
    expect(screen.queryByRole("button", { name: "Remove tag a" })).toBeNull();
    expect(screen.getByRole("button", { name: "Remove tag b" })).toBeTruthy();
  });

  it("adds on Enter and on a comma, and ignores a duplicate", () => {
    render(<Harness initial={{ title: "T", summary: "", slug: "s", tags: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add a tag" }));
    const input = screen.getByLabelText("Tags") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "maths" } });
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.change(input, { target: { value: "physics," } });
    fireEvent.change(input, { target: { value: "MATHS" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByRole("button", { name: "Remove tag maths" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove tag physics" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Remove tag MATHS" })).toBeNull();
  });

  it("removes the last tag on Backspace in the empty input", () => {
    render(<Harness initial={{ title: "T", summary: "", slug: "s", tags: ["a", "b"] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add a tag" }));
    const input = screen.getByLabelText("Tags");
    fireEvent.keyDown(input, { key: "Backspace" });
    expect(screen.queryByRole("button", { name: "Remove tag b" })).toBeNull();
    expect(screen.getByRole("button", { name: "Remove tag a" })).toBeTruthy();
  });

  it("does not call onTags when an empty tag input loses focus or Backspace has no tags", () => {
    const onTags = vi.fn();
    render(
      <PostDetails
        title="T"
        summary=""
        slug="s"
        tags={[]}
        slugLocked={false}
        preview={false}
        onTitle={() => {}}
        onSummary={() => {}}
        onSlug={() => {}}
        onTags={onTags}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Add a tag" }));
    const input = screen.getByLabelText("Tags");
    fireEvent.keyDown(input, { key: "Backspace" });
    fireEvent.blur(input);
    expect(onTags).not.toHaveBeenCalled();
  });

  it("keeps what was typed when the input loses focus", () => {
    render(<Harness initial={{ title: "T", summary: "", slug: "s", tags: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add a tag" }));
    const input = screen.getByLabelText("Tags");
    fireEvent.change(input, { target: { value: "late" } });
    fireEvent.blur(input);
    expect(screen.getByRole("button", { name: "Remove tag late" })).toBeTruthy();
    expect(screen.queryByLabelText("Tags")).toBeNull();
  });
});

describe("preview", () => {
  it("shows the details as plain text without any control", () => {
    render(<Harness preview />);
    expect(screen.queryByLabelText("Title")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Hello");
    expect(screen.getByText("Sum")).toBeTruthy();
    expect(screen.getByText("/hello")).toBeTruthy();
    expect(screen.getByText("maths")).toBeTruthy();
  });
});
