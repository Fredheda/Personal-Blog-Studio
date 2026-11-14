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
    ...overrides,
  };
}

test("lists the posts with a link to each editor", async () => {
  const api = fakeApi({
    listPosts: async () => [
      { postId: "01AAAAAAAAAAAAAAAAAAAAAAAA", title: "First", slug: "first", updatedAt: "2026-11-10T10:00:00Z" },
      { postId: "01BBBBBBBBBBBBBBBBBBBBBBBB", title: "", slug: "", updatedAt: "2026-11-09T10:00:00Z" },
    ],
  });
  render(<Posts api={api} />);
  const first = await screen.findByRole("link", { name: "First" });
  expect(first.getAttribute("href")).toBe("/posts/01AAAAAAAAAAAAAAAAAAAAAAAA");
  expect(screen.getByRole("link", { name: "(untitled)" })).toBeTruthy();
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
