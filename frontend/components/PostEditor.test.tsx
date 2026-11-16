import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ApiError } from "../lib/problem";
import type { Draft, StudioApi } from "../lib/studio-api";
import { PostEditor } from "./PostEditor";

// The real editor is covered in CrepeEditor.test.tsx; here a textarea stands in.
vi.mock("./CrepeEditor", () => ({
  CrepeEditor: ({ initial, onChange }: { initial: string; onChange: (text: string) => void }) => (
    <textarea aria-label="Body (Markdown)" defaultValue={initial} onChange={(e) => onChange(e.target.value)} />
  ),
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const draft: Draft = {
  postId: "01AAAAAAAAAAAAAAAAAAAAAAAA",
  title: "Hello",
  slug: "hello",
  summary: "Sum",
  tags: ["maths"],
  coverMediaId: null,
  createdAt: "2026-11-10T10:00:00Z",
  updatedAt: "2026-11-10T10:00:00Z",
  body: "# Hi",
  bodyEtag: '"b1"',
  metaEtag: '"m1"',
  published: false,
  version: null,
  publishedAt: null,
  versionPublishedAt: null,
  slugLocked: false,
};

function fakeApi(overrides: Partial<StudioApi> = {}): StudioApi {
  const unused = async () => {
    throw new Error("unused");
  };
  return {
    listPosts: unused,
    createPost: unused,
    getPost: async () => draft,
    saveBody: unused,
    patchMeta: unused,
    publish: unused,
    unpublish: async () => undefined,
    ...overrides,
  } as StudioApi;
}

const problem = (status: number, title: string, detail?: string) =>
  new ApiError(status, { type: "about:blank", title, status, detail });
const saveButton = () => screen.getByRole("button", { name: "Save" }) as HTMLButtonElement;
const publishButton = () => screen.getByRole("button", { name: "Publish" }) as HTMLButtonElement;

test("loads the post into the form and the editor", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi()} />);
  expect(((await screen.findByLabelText("Title")) as HTMLInputElement).value).toBe("Hello");
  expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("hello");
  expect((screen.getByLabelText("Tags (comma separated, optional)") as HTMLInputElement).value).toBe("maths");
  expect((await screen.findByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("# Hi");
});

test("a load failure that is not a lost session says what failed", async () => {
  const getPost = vi.fn(async () => {
    throw problem(404, "Not Found");
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ getPost })} />);
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("Not Found");
  expect(alert.textContent).not.toMatch(/session may have expired/i);
});

// --- body autosave ---

test("typing autosaves once after the pause, with the loaded ETag, and says Saved", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const saveBody = vi.fn(async (...args: [string, string, string]) => ({ ...draft, body: args[1], bodyEtag: '"b2"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  const box = await screen.findByLabelText("Body (Markdown)");
  fireEvent.change(box, { target: { value: "a" } });
  fireEvent.change(box, { target: { value: "ab" } });
  await vi.advanceTimersByTimeAsync(1600);
  await waitFor(() => expect(saveBody).toHaveBeenCalledTimes(1));
  expect(saveBody).toHaveBeenCalledWith(draft.postId, "ab", '"b1"');
  expect(await screen.findByText("Saved")).toBeTruthy();
});

test("the second autosave sends the ETag the first one returned", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let n = 1;
  const saveBody = vi.fn(async (...args: [string, string, string]) => ({ ...draft, body: args[1], bodyEtag: `"b${++n}"` }));
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  const box = await screen.findByLabelText("Body (Markdown)");
  fireEvent.change(box, { target: { value: "one" } });
  await vi.advanceTimersByTimeAsync(1600);
  await waitFor(() => expect(saveBody).toHaveBeenCalledTimes(1));
  fireEvent.change(box, { target: { value: "two" } });
  await vi.advanceTimersByTimeAsync(1600);
  await waitFor(() => expect(saveBody).toHaveBeenCalledTimes(2));
  expect(saveBody.mock.calls[0][2]).toBe('"b1"');
  expect(saveBody.mock.calls[1][2]).toBe('"b2"');
});

test("a failed autosave shows its reason and the text stays; the next good save clears it", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const saveBody = vi
    .fn()
    .mockRejectedValueOnce(problem(413, "Content Too Large", "the request body is too large"))
    .mockImplementation(async (...args: [string, string, string]) => ({ ...draft, body: args[1], bodyEtag: '"b2"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  const box = await screen.findByLabelText("Body (Markdown)");
  fireEvent.change(box, { target: { value: "big" } });
  await vi.advanceTimersByTimeAsync(1600);
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("Content Too Large");
  expect(alert.textContent).toContain("the request body is too large");
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("big");
  fireEvent.change(box, { target: { value: "smaller" } });
  await vi.advanceTimersByTimeAsync(1600);
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(await screen.findByText("Saved")).toBeTruthy();
});

test("a body save that gets no answer says the session may have expired and keeps the text", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const saveBody = vi.fn(async () => {
    throw new ApiError(0, null);
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "mine" } });
  await vi.advanceTimersByTimeAsync(1600);
  expect((await screen.findByRole("alert")).textContent).toMatch(/session may have expired/i);
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("mine");
});

test("a 412 from autosave shows the reload banner and keeps the text", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const saveBody = vi.fn(async () => {
    throw problem(412, "Precondition Failed");
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "mine" } });
  await vi.advanceTimersByTimeAsync(1600);
  expect(await screen.findByText(/changed elsewhere/i)).toBeTruthy();
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("mine");
  expect(screen.getByRole("button", { name: "Reload the post" })).toBeTruthy();
});

// --- one Save button ---

test("Save with only the details changed calls patchMeta and no saveBody", async () => {
  const patchMeta = vi.fn(async () => ({ ...draft, slug: "hello-2", metaEtag: '"m2"' }));
  const saveBody = vi.fn();
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta, saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Slug"), { target: { value: "hello-2" } });
  fireEvent.click(saveButton());
  await waitFor(() => expect(patchMeta).toHaveBeenCalledTimes(1));
  expect(patchMeta).toHaveBeenCalledWith(draft.postId, { title: "Hello", slug: "hello-2", summary: "Sum", tags: ["maths"] }, '"m1"');
  expect(saveBody).not.toHaveBeenCalled();
});

test("Save with only the body changed calls saveBody and no patchMeta", async () => {
  const patchMeta = vi.fn();
  const saveBody = vi.fn(async (...args: [string, string, string]) => ({ ...draft, body: args[1], bodyEtag: '"b2"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta, saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "# Changed" } });
  fireEvent.click(saveButton());
  await waitFor(() => expect(saveBody).toHaveBeenCalledWith(draft.postId, "# Changed", '"b1"'));
  expect(patchMeta).not.toHaveBeenCalled();
});

test("Save with both changed sends the details first, each with its own ETag, not the newer body ETag a details answer carries", async () => {
  const calls: string[] = [];
  const patchMeta = vi.fn(async (...args: [string, unknown, string]) => {
    calls.push(`details ${args[2]}`);
    return { ...draft, slug: "hello-2", metaEtag: '"m2"', bodyEtag: '"b9"' };
  });
  const saveBody = vi.fn(async (...args: [string, string, string]) => {
    calls.push(`body ${args[2]}`);
    return { ...draft, body: args[1], bodyEtag: '"b2"' };
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta, saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Slug"), { target: { value: "hello-2" } });
  fireEvent.change(screen.getByLabelText("Body (Markdown)"), { target: { value: "# New" } });
  fireEvent.click(saveButton());
  await waitFor(() => expect(saveBody).toHaveBeenCalled());
  expect(calls).toEqual(['details "m1"', 'body "b1"']);
});

test("tags typed as 'a, b' are sent as two tags", async () => {
  const patchMeta = vi.fn(async () => ({ ...draft, tags: ["a", "b"], metaEtag: '"m2"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta })} />);
  fireEvent.change(await screen.findByLabelText("Tags (comma separated, optional)"), { target: { value: "a, b" } });
  fireEvent.click(saveButton());
  await waitFor(() =>
    expect(patchMeta).toHaveBeenCalledWith(draft.postId, { title: "Hello", slug: "hello", summary: "Sum", tags: ["a", "b"] }, '"m1"'),
  );
});

test("a body 412 after the details saved in the same Save shows the banner and keeps both texts", async () => {
  const patchMeta = vi.fn(async () => ({ ...draft, slug: "hello-2", metaEtag: '"m2"' }));
  const saveBody = vi.fn(async () => {
    throw problem(412, "Precondition Failed");
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta, saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Slug"), { target: { value: "hello-2" } });
  fireEvent.change(screen.getByLabelText("Body (Markdown)"), { target: { value: "typed text" } });
  fireEvent.click(saveButton());
  expect(await screen.findByText(/changed elsewhere/i)).toBeTruthy();
  expect(patchMeta).toHaveBeenCalledTimes(1);
  expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("hello-2");
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("typed text");
  expect(screen.getByRole("button", { name: "Reload the post" })).toBeTruthy();
});

test("leaving with unsaved details warns, and not once they are saved", async () => {
  const patchMeta = vi.fn(async () => ({ ...draft, title: "New", metaEtag: '"m2"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta })} />);
  fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "New" } });
  const dirty = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(dirty);
  expect(dirty.defaultPrevented).toBe(true);
  fireEvent.click(saveButton());
  await waitFor(() => expect(patchMeta).toHaveBeenCalled());
  await waitFor(() => expect(saveButton().disabled).toBe(true));
  const clean = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(clean);
  expect(clean.defaultPrevented).toBe(false);
});

test("after Reload the post, the old controller's late closing flush changes nothing on screen", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let releaseOld: () => void = () => {};
  const saveBody = vi
    .fn()
    .mockRejectedValueOnce(problem(412, "Precondition Failed"))
    .mockImplementation(async () => {
      await new Promise<void>((resolve) => (releaseOld = resolve));
      throw problem(422, "Unprocessable Content", "late old error");
    });
  const getPost = vi.fn(async () => draft);
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody, getPost })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "mine" } });
  await vi.advanceTimersByTimeAsync(1600);
  fireEvent.click(await screen.findByRole("button", { name: "Reload the post" }));
  await waitFor(() => expect(getPost).toHaveBeenCalledTimes(2));
  releaseOld();
  await vi.advanceTimersByTimeAsync(10);
  expect(screen.queryByText(/late old error/)).toBeNull();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a details 412 shows the banner, answers not saved, and the typed body is still sent", async () => {
  const patchMeta = vi.fn(async () => {
    throw problem(412, "Precondition Failed");
  });
  const saveBody = vi.fn(async (...args: [string, string, string]) => ({ ...draft, body: args[1], bodyEtag: '"b2"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta, saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Slug"), { target: { value: "hello-2" } });
  fireEvent.change(screen.getByLabelText("Body (Markdown)"), { target: { value: "typed text" } });
  fireEvent.click(saveButton());
  expect(await screen.findByText(/changed elsewhere/i)).toBeTruthy();
  await waitFor(() => expect(saveBody).toHaveBeenCalledWith(draft.postId, "typed text", '"b1"'));
  expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("hello-2");
});

test("a second click during a save sends nothing more", async () => {
  let release: () => void = () => {};
  const patchMeta = vi.fn(async () => {
    await new Promise<void>((resolve) => (release = resolve));
    return { ...draft, slug: "hello-2", metaEtag: '"m2"' };
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta })} />);
  fireEvent.change(await screen.findByLabelText("Slug"), { target: { value: "hello-2" } });
  fireEvent.click(saveButton());
  await waitFor(() => expect(patchMeta).toHaveBeenCalledTimes(1));
  expect(saveButton().disabled).toBe(true);
  fireEvent.click(saveButton());
  fireEvent.click(saveButton());
  release();
  await waitFor(() => expect(saveButton().disabled).toBe(true)); // nothing unsaved any more
  expect(patchMeta).toHaveBeenCalledTimes(1);
});

test("a failed save shows the API's reason, not just its title", async () => {
  const patchMeta = vi.fn(async () => {
    throw problem(403, "Forbidden", "origin not allowed");
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta })} />);
  fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "New" } });
  fireEvent.click(saveButton());
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("Forbidden");
  expect(alert.textContent).toContain("origin not allowed");
});

test("tags are optional: clearing the box saves an empty list, and a post without tags publishes", async () => {
  const patchMeta = vi.fn(async () => ({ ...draft, tags: [], metaEtag: '"m2"' }));
  const publish = vi.fn(async () => ({ postId: draft.postId, slug: "hello", version: 1, publishedAt: "t", updatedAt: "t" }));
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta, publish })} />);
  fireEvent.change(await screen.findByLabelText("Tags (comma separated, optional)"), { target: { value: "" } });
  fireEvent.click(saveButton());
  await waitFor(() =>
    expect(patchMeta).toHaveBeenCalledWith(draft.postId, { title: "Hello", slug: "hello", summary: "Sum", tags: [] }, '"m1"'),
  );
  await waitFor(() => expect(publishButton().disabled).toBe(false));
  fireEvent.click(publishButton());
  await waitFor(() => expect(publish).toHaveBeenCalledWith(draft.postId, '"b1"'));
});

// --- Publish waits for saved edits ---

test("Publish is disabled while anything is unsaved; after Save it publishes with the new body ETag", async () => {
  const saveBody = vi.fn(async (...args: [string, string, string]) => ({ ...draft, body: args[1], bodyEtag: '"b2"' }));
  const publish = vi.fn(async () => ({ postId: draft.postId, slug: "hello", version: 1, publishedAt: "t", updatedAt: "t" }));
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody, publish })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "fresh" } });
  expect(publishButton().disabled).toBe(true);
  fireEvent.click(saveButton());
  await waitFor(() => expect(saveBody).toHaveBeenCalledWith(draft.postId, "fresh", '"b1"'));
  await waitFor(() => expect(publishButton().disabled).toBe(false));
  fireEvent.click(publishButton());
  await waitFor(() => expect(publish).toHaveBeenCalledWith(draft.postId, '"b2"'));
  expect(await screen.findByText(/Published as version 1/)).toBeTruthy();
});

test("Publish stays disabled with unsaved details, and after a failed Save of either half", async () => {
  const publish = vi.fn();
  const failingDetails = vi.fn(async () => {
    throw problem(422, "Unprocessable Content", "slug is not valid");
  });
  const { unmount } = render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta: failingDetails, publish })} />);
  fireEvent.change(await screen.findByLabelText("Slug"), { target: { value: "Bad Slug" } });
  expect(publishButton().disabled).toBe(true);
  fireEvent.click(saveButton());
  await screen.findByText(/slug is not valid/);
  expect(publishButton().disabled).toBe(true);
  expect(publish).not.toHaveBeenCalled();
  unmount();

  const failingBody = vi.fn(async () => {
    throw problem(422, "Unprocessable Content", "body is larger than 200000 bytes");
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody: failingBody, publish })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "x" } });
  fireEvent.click(saveButton());
  await screen.findByText(/body is larger than/);
  expect(publishButton().disabled).toBe(true);
  expect(publish).not.toHaveBeenCalled();
});

test("a refused publish lists every problem with its line", async () => {
  const publish = vi.fn(async () => {
    throw new ApiError(422, {
      type: "about:blank",
      title: "Unprocessable Content",
      status: 422,
      problems: [
        { line: 3, message: "raw HTML is not allowed" },
        { line: 0, message: "slug is required" },
      ],
    });
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ publish })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Publish" }));
  expect(await screen.findByText("Line 3: raw HTML is not allowed")).toBeTruthy();
  expect(screen.getByText("slug is required")).toBeTruthy();
  expect(publish).toHaveBeenCalledWith(draft.postId, '"b1"');
});

test("a successful publish says which version went live, and unpublish clears it", async () => {
  const publish = vi.fn(async () => ({ postId: draft.postId, slug: "hello", version: 2, publishedAt: "t", updatedAt: "t" }));
  const unpublish = vi.fn(async () => undefined);
  render(<PostEditor id={draft.postId} api={fakeApi({ publish, unpublish })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Publish" }));
  expect(await screen.findByText(/Published as version 2\. It is live at \/blog\/hello\./)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Unpublish" }));
  await waitFor(() => expect(unpublish).toHaveBeenCalledWith(draft.postId));
  expect(
    await screen.findByText(/Unpublished\. \/blog\/hello can stay on the live site for a few seconds\./),
  ).toBeTruthy();
});

test("Publish is disabled once autosave hit an error or a conflict", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const saveBody = vi.fn(async () => {
    throw problem(422, "Unprocessable Content");
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "bad" } });
  await vi.advanceTimersByTimeAsync(1600);
  await screen.findByRole("alert");
  expect(publishButton().disabled).toBe(true);
});

// --- preview ---

test("the Preview tab renders the typed Markdown, maths as MathML, and keeps the editor text", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi()} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "# Big\n\n$a^2$" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview" }));
  expect(document.querySelector(".preview h1")?.textContent).toBe("Big");
  expect(document.querySelectorAll(".preview math").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("# Big\n\n$a^2$");
});
