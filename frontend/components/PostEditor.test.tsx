import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ApiError } from "../lib/problem";
import type { Draft, StudioApi } from "../lib/studio-api";
import { PostEditor } from "./PostEditor";

afterEach(cleanup);

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

test("loads the post into the form and the textarea", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi()} />);
  expect(((await screen.findByLabelText("Title")) as HTMLInputElement).value).toBe("Hello");
  expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("hello");
  expect((screen.getByLabelText("Tags (comma separated)") as HTMLInputElement).value).toBe("maths");
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("# Hi");
});

test("saving the body sends the loaded ETag and then uses the new one", async () => {
  const saveBody = vi.fn(async (...args: [string, string, string]) => ({ ...draft, body: args[1], bodyEtag: '"b2"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "# Changed" } });
  fireEvent.click(screen.getByRole("button", { name: "Save body" }));
  await waitFor(() => expect(saveBody).toHaveBeenCalledWith(draft.postId, "# Changed", '"b1"'));
  fireEvent.change(screen.getByLabelText("Body (Markdown)"), { target: { value: "# Again" } });
  fireEvent.click(screen.getByRole("button", { name: "Save body" }));
  await waitFor(() => expect(saveBody).toHaveBeenLastCalledWith(draft.postId, "# Again", '"b2"'));
});

test("saving details patches the changed fields with the meta ETag and splits the tags", async () => {
  const patchMeta = vi.fn(async () => ({ ...draft, title: "New", metaEtag: '"m2"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta })} />);
  fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "New" } });
  fireEvent.change(screen.getByLabelText("Tags (comma separated)"), { target: { value: "maths, python ,," } });
  fireEvent.click(screen.getByRole("button", { name: "Save details" }));
  await waitFor(() =>
    expect(patchMeta).toHaveBeenCalledWith(
      draft.postId,
      { title: "New", slug: "hello", summary: "Sum", tags: ["maths", "python"] },
      '"m1"',
    ),
  );
});

test("saving details does not adopt the server's newer body ETag: a body changed in another tab still gets a 412", async () => {
  // The details save answers with a draft whose body already changed elsewhere.
  const patchMeta = vi.fn(async () => ({ ...draft, title: "New", metaEtag: '"m2"', bodyEtag: '"b9"', body: "changed elsewhere" }));
  const saveBody = vi.fn(async (...args: [string, string, string]) => ({ ...draft, body: args[1], bodyEtag: '"b10"' }));
  render(<PostEditor id={draft.postId} api={fakeApi({ patchMeta, saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "New" } });
  fireEvent.click(screen.getByRole("button", { name: "Save details" }));
  await waitFor(() => expect(patchMeta).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText("Body (Markdown)"), { target: { value: "my edit" } });
  fireEvent.click(screen.getByRole("button", { name: "Save body" }));
  await waitFor(() => expect(saveBody).toHaveBeenCalled());
  expect(saveBody.mock.calls[0][2]).toBe('"b1"'); // the ETag the textarea was based on
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).not.toBe("changed elsewhere");
});

test("a load failure that is not a lost session says what failed", async () => {
  const getPost = vi.fn(async () => {
    throw new ApiError(404, { type: "about:blank", title: "Not Found", status: 404 });
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ getPost })} />);
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("Not Found");
  expect(alert.textContent).not.toMatch(/session may have expired/i);
});

test("a 412 asks for a reload and keeps what the owner typed", async () => {
  const saveBody = vi.fn(async () => {
    throw new ApiError(412, { type: "about:blank", title: "Precondition Failed", status: 412 });
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "mine" } });
  fireEvent.click(screen.getByRole("button", { name: "Save body" }));
  expect(await screen.findByText(/changed elsewhere/i)).toBeTruthy();
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("mine");
  expect(screen.getByRole("button", { name: "Reload the post" })).toBeTruthy();
});

test("a save that gets no answer says the session may have expired and keeps the text", async () => {
  const saveBody = vi.fn(async () => {
    throw new ApiError(0, null);
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "mine" } });
  fireEvent.click(screen.getByRole("button", { name: "Save body" }));
  expect((await screen.findByRole("alert")).textContent).toMatch(/session may have expired/i);
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("mine");
});

test("the owner's order: details typed but not saved keep Publish disabled after the body is saved; Save details enables it", async () => {
  const blank: Draft = { ...draft, title: "Hello world", slug: "", summary: "", tags: [], body: "" };
  const saveBody = vi.fn(async (_id: string, body: string, _etag: string) => ({ ...blank, body, bodyEtag: '"b2"' }));
  const patchMeta = vi.fn(async () => ({ ...blank, slug: "hello", summary: "Sum", metaEtag: '"m2"' }));
  const publish = vi.fn(async () => ({ postId: draft.postId, slug: "hello", version: 1, publishedAt: "t", updatedAt: "t" }));
  render(<PostEditor id={draft.postId} api={fakeApi({ getPost: async () => blank, saveBody, patchMeta, publish })} />);
  const publishButton = (await screen.findByRole("button", { name: "Publish" })) as HTMLButtonElement;

  fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "hello" } });
  fireEvent.change(screen.getByLabelText("Summary"), { target: { value: "Sum" } });
  fireEvent.change(screen.getByLabelText("Body (Markdown)"), { target: { value: "# Hello" } });
  fireEvent.click(screen.getByRole("button", { name: "Save body" }));
  await waitFor(() => expect(saveBody).toHaveBeenCalled());
  // The body is saved, the details are not: Publish stays disabled.
  expect(publishButton.disabled).toBe(true);
  expect(publishButton.title).toBe("Save your edits first");

  fireEvent.click(screen.getByRole("button", { name: "Save details" }));
  await waitFor(() => expect(patchMeta).toHaveBeenCalled());
  await waitFor(() => expect(publishButton.disabled).toBe(false));
  fireEvent.click(publishButton);
  await waitFor(() => expect(publish).toHaveBeenCalledWith(draft.postId, '"b2"'));
});

test("publish is disabled while there are unsaved edits", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi()} />);
  const publish = (await screen.findByRole("button", { name: "Publish" })) as HTMLButtonElement;
  expect(publish.disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("Body (Markdown)"), { target: { value: "x" } });
  expect(publish.disabled).toBe(true);
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
  expect(await screen.findByText(/Published as version 2/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Unpublish" }));
  await waitFor(() => expect(unpublish).toHaveBeenCalledWith(draft.postId));
  expect(await screen.findByText(/Unpublished/)).toBeTruthy();
});
