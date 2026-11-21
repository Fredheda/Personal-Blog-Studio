import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ApiError } from "../lib/problem";
import type { StudioApi } from "../lib/studio-api";
import { Posts } from "./Posts";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

afterEach(() => {
  cleanup();
  push.mockReset();
  vi.restoreAllMocks();
});

function fakeApi(overrides: Partial<StudioApi> = {}): StudioApi {
  return {
    listPosts: async () => [],
    createPost: async () => {
      throw new Error("unused");
    },
    getPost: async () => {
      throw new Error("unused");
    },
    saveBody: async () => {
      throw new Error("unused");
    },
    patchMeta: async () => {
      throw new Error("unused");
    },
    publish: async () => {
      throw new Error("unused");
    },
    unpublish: async () => undefined,
    checkPost: async () => {
      throw new Error("unused");
    },
    deletePost: async () => undefined,
    ...overrides,
  };
}

test("lists the posts with a link to each editor", async () => {
  const api = fakeApi({
    listPosts: async () => [
      {
        postId: "01AAAAAAAAAAAAAAAAAAAAAAAA",
        title: "First",
        slug: "first",
        updatedAt: "2026-11-10T10:00:00Z",
        published: false,
        version: null,
        publishedAt: null,
        versionPublishedAt: null,
      },
      {
        postId: "01BBBBBBBBBBBBBBBBBBBBBBBB",
        title: "",
        slug: "",
        updatedAt: "2026-11-09T10:00:00Z",
        published: false,
        version: null,
        publishedAt: null,
        versionPublishedAt: null,
      },
    ],
  });
  render(<Posts api={api} />);
  const first = await screen.findByRole("link", { name: "First" });
  expect(first.getAttribute("href")).toBe("/posts/01AAAAAAAAAAAAAAAAAAAAAAAA");
  expect(screen.getByRole("link", { name: "(untitled)" })).toBeTruthy();
});

test("each row says whether the post is live as a pill; a post published and then unpublished is a draft", async () => {
  const base = { updatedAt: "2026-11-10T10:00:00Z", versionPublishedAt: null };
  const api = fakeApi({
    listPosts: async () => [
      { ...base, postId: "01AAAAAAAAAAAAAAAAAAAAAAAA", title: "Live", slug: "live", published: true, version: 1, publishedAt: "2026-11-10T09:00:00Z" },
      { ...base, postId: "01BBBBBBBBBBBBBBBBBBBBBBBB", title: "Off", slug: "off", published: false, version: null, publishedAt: null },
    ],
  });
  render(<Posts api={api} />);
  const live = await screen.findByText(/Published, version 1/);
  expect(live.className).toContain("rounded-full");
  expect(screen.getByText(/Draft/)).toBeTruthy();
});

test("says so when there are no posts", async () => {
  render(<Posts api={fakeApi()} />);
  expect(await screen.findByText("No posts yet.")).toBeTruthy();
});

test("creating a post opens its editor", async () => {
  const createPost = vi.fn(async (title: string) => ({ postId: "01CCCCCCCCCCCCCCCCCCCCCCCC", title }) as never);
  render(<Posts api={fakeApi({ createPost })} />);
  fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "My post" } });
  fireEvent.click(screen.getByRole("button", { name: "Create post" }));
  await waitFor(() => expect(push).toHaveBeenCalledWith("/posts/01CCCCCCCCCCCCCCCCCCCCCCCC"));
  expect(createPost).toHaveBeenCalledWith("My post");
});

test("a failed list shows the session message, not an empty list", async () => {
  render(<Posts api={fakeApi({ listPosts: async () => Promise.reject(new Error("x")) })} />);
  expect((await screen.findByRole("alert")).textContent).toMatch(/session may have expired/i);
  expect(screen.queryByText("No posts yet.")).toBeNull();
});

test("a create that gets no answer says the session may have expired", async () => {
  const createPost = vi.fn(async () => {
    throw new ApiError(0, null);
  });
  render(<Posts api={fakeApi({ createPost })} />);
  fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "T" } });
  fireEvent.click(screen.getByRole("button", { name: "Create post" }));
  expect((await screen.findByRole("alert")).textContent).toMatch(/session may have expired/i);
});

const ID = "01AAAAAAAAAAAAAAAAAAAAAAAA";
const row = {
  postId: ID,
  title: "First",
  slug: "first",
  updatedAt: "2026-11-10T10:00:00Z",
  published: false,
  version: null,
  publishedAt: null,
  versionPublishedAt: null,
};
const live = { ...row, published: true, version: 1, publishedAt: "2026-11-10T09:00:00Z" };
const confirmation = new ApiError(409, {
  type: "urn:blog-studio:confirmation-required",
  title: "Confirmation required",
  status: 409,
});

async function press(name: string) {
  fireEvent.click(await screen.findByRole("button", { name }));
}

test("Delete asks in a dialog, deletes a draft and removes its row", async () => {
  const deletePost = vi.fn(async () => undefined);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  await press("Delete First");
  const dialog = await screen.findByRole("dialog", { name: "Delete this draft?" });
  expect(dialog.textContent).toContain('"First" and its revisions are removed. You can get it back for 7 days by asking.');
  fireEvent.click(screen.getByRole("button", { name: "Delete draft" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "First" })).toBeNull());
  expect(deletePost).toHaveBeenCalledTimes(1);
  expect(deletePost).toHaveBeenCalledWith(ID);
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("Keep it closes the dialog and sends nothing; Escape does the same", async () => {
  const deletePost = vi.fn(async () => undefined);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  await press("Delete First");
  await screen.findByRole("dialog");
  fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  await press("Delete First");
  fireEvent.keyDown(await screen.findByRole("dialog"), { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(deletePost).not.toHaveBeenCalled();
  expect(screen.getByRole("link", { name: "First" })).toBeTruthy();
});

test("a post that is published now asks once, in the post dialog, and deletes with confirm", async () => {
  const deletePost = vi.fn(async () => undefined);
  render(<Posts api={fakeApi({ listPosts: async () => [live], deletePost })} />);
  await press("Delete First");
  const dialog = await screen.findByRole("dialog", { name: "Delete this post?" });
  expect(dialog.textContent).toContain(
    '"First" is taken off the blog and removed, with its published versions. You can get it back for 7 days by asking.',
  );
  fireEvent.click(screen.getByRole("button", { name: "Delete post" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "First" })).toBeNull());
  expect(deletePost).toHaveBeenCalledTimes(1);
  expect(deletePost).toHaveBeenCalledWith(ID, { confirm: "published" });
});

test("a post published earlier asks the draft question, then the post question the API asks for", async () => {
  const deletePost = vi
    .fn<StudioApi["deletePost"]>()
    .mockRejectedValueOnce(confirmation)
    .mockResolvedValueOnce(undefined);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  await press("Delete First");
  fireEvent.click(await screen.findByRole("button", { name: "Delete draft" }));
  await screen.findByRole("dialog", { name: "Delete this post?" });
  expect(deletePost).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Delete post" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "First" })).toBeNull());
  expect(deletePost).toHaveBeenNthCalledWith(1, ID);
  expect(deletePost).toHaveBeenNthCalledWith(2, ID, { confirm: "published" });
});

test("keeping the post at the second question sends no second delete", async () => {
  const deletePost = vi.fn<StudioApi["deletePost"]>().mockRejectedValueOnce(confirmation);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  await press("Delete First");
  fireEvent.click(await screen.findByRole("button", { name: "Delete draft" }));
  await screen.findByRole("dialog", { name: "Delete this post?" });
  fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(deletePost).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("link", { name: "First" })).toBeTruthy();
});

test("another 409 shows an error and never opens the post dialog", async () => {
  const busy = new ApiError(409, { type: "about:blank", title: "Conflict", status: 409 });
  const deletePost = vi.fn<StudioApi["deletePost"]>().mockRejectedValue(busy);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  await press("Delete First");
  fireEvent.click(await screen.findByRole("button", { name: "Delete draft" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByRole("link", { name: "First" })).toBeTruthy();
});

test("a 404 means it is already gone: the row leaves and no error shows", async () => {
  const deletePost = vi.fn<StudioApi["deletePost"]>().mockRejectedValue(new ApiError(404, null));
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  await press("Delete First");
  fireEvent.click(await screen.findByRole("button", { name: "Delete draft" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "First" })).toBeNull());
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a delete that gets no answer says the session may have expired and keeps the row", async () => {
  const deletePost = vi.fn<StudioApi["deletePost"]>().mockRejectedValue(new ApiError(0, null));
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  await press("Delete First");
  fireEvent.click(await screen.findByRole("button", { name: "Delete draft" }));
  expect((await screen.findByRole("alert")).textContent).toMatch(/session may have expired/i);
  expect(screen.getByRole("link", { name: "First" })).toBeTruthy();
});
