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

test("each row says whether the post is live; a post published and then unpublished is a draft", async () => {
  const base = { updatedAt: "2026-11-10T10:00:00Z", versionPublishedAt: null };
  const api = fakeApi({
    listPosts: async () => [
      { ...base, postId: "01AAAAAAAAAAAAAAAAAAAAAAAA", title: "Live", slug: "live", published: true, version: 1, publishedAt: "2026-11-10T09:00:00Z" },
      { ...base, postId: "01BBBBBBBBBBBBBBBBBBBBBBBB", title: "Off", slug: "off", published: false, version: null, publishedAt: null },
    ],
  });
  render(<Posts api={api} />);
  expect(await screen.findByText(/Published, version 1/)).toBeTruthy();
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
const confirmation = new ApiError(409, {
  type: "urn:blog-studio:confirmation-required",
  title: "Confirmation required",
  status: 409,
});

function ask(...answers: boolean[]) {
  const spy = vi.spyOn(window, "confirm");
  for (const answer of answers) spy.mockReturnValueOnce(answer);
  return spy;
}

test("Delete asks once, deletes a draft and removes its row", async () => {
  const deletePost = vi.fn(async () => undefined);
  const confirm = ask(true);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Delete First" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "First" })).toBeNull());
  expect(confirm).toHaveBeenCalledTimes(1);
  expect(confirm).toHaveBeenCalledWith('Delete "First"? You can get it back for 7 days by asking.');
  expect(deletePost).toHaveBeenCalledTimes(1);
  expect(deletePost).toHaveBeenCalledWith(ID);
});

test("cancelling the first confirmation sends nothing and keeps the row", async () => {
  const deletePost = vi.fn(async () => undefined);
  ask(false);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Delete First" }));
  expect(deletePost).not.toHaveBeenCalled();
  expect(screen.getByRole("link", { name: "First" })).toBeTruthy();
});

test("a post published once asks the stronger question, then deletes with confirm", async () => {
  const deletePost = vi
    .fn<StudioApi["deletePost"]>()
    .mockRejectedValueOnce(confirmation)
    .mockResolvedValueOnce(undefined);
  const confirm = ask(true, true);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Delete First" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "First" })).toBeNull());
  expect(confirm).toHaveBeenNthCalledWith(
    2,
    "It was published: deleting takes it off the public site and removes it. You can get it back for 7 days by asking.",
  );
  expect(deletePost).toHaveBeenNthCalledWith(1, ID);
  expect(deletePost).toHaveBeenNthCalledWith(2, ID, { confirm: "published" });
});

test("cancelling the stronger question keeps the post and sends no second delete", async () => {
  const deletePost = vi.fn<StudioApi["deletePost"]>().mockRejectedValueOnce(confirmation);
  const confirm = ask(true, false);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Delete First" }));
  await waitFor(() => expect(confirm).toHaveBeenCalledTimes(2));
  expect(deletePost).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("link", { name: "First" })).toBeTruthy();
});

test("another 409 shows an error and never opens the stronger question", async () => {
  const busy = new ApiError(409, { type: "about:blank", title: "Conflict", status: 409 });
  const deletePost = vi.fn<StudioApi["deletePost"]>().mockRejectedValue(busy);
  const confirm = ask(true);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Delete First" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(confirm).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("link", { name: "First" })).toBeTruthy();
});

test("a 404 means it is already gone: the row leaves and no error shows", async () => {
  const deletePost = vi.fn<StudioApi["deletePost"]>().mockRejectedValue(new ApiError(404, null));
  ask(true);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Delete First" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "First" })).toBeNull());
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a delete that gets no answer says the session may have expired and keeps the row", async () => {
  const deletePost = vi.fn<StudioApi["deletePost"]>().mockRejectedValue(new ApiError(0, null));
  ask(true);
  render(<Posts api={fakeApi({ listPosts: async () => [row], deletePost })} />);
  fireEvent.click(await screen.findByRole("button", { name: "Delete First" }));
  expect((await screen.findByRole("alert")).textContent).toMatch(/session may have expired/i);
  expect(screen.getByRole("link", { name: "First" })).toBeTruthy();
});
