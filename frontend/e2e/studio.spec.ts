import { expect, test, type APIRequestContext, type APIResponse } from "@playwright/test";

import { API_ORIGIN } from "./ports.ts";

// The API behind the web app is the real studio API, so these helpers use its
// real rules: the custom header on every write and the ETag in If-Match.
const HEADERS = { "x-blog-studio": "1" };

type Seed = { title: string; slug?: string; summary?: string; body?: string };

const unique = (label: string) => `${label} ${Math.random().toString(36).slice(2, 8)}`;

async function must(response: APIResponse): Promise<APIResponse> {
  expect(response.ok(), await response.text()).toBeTruthy();
  return response;
}

async function createPost(request: APIRequestContext, seed: Seed): Promise<{ postId: string }> {
  const created = await (
    await must(await request.post(`${API_ORIGIN}/posts`, { headers: HEADERS, data: { title: seed.title } }))
  ).json();
  const id: string = created.postId;
  if (seed.slug || seed.summary) {
    await must(
      await request.patch(`${API_ORIGIN}/posts/${id}/meta`, {
        headers: { ...HEADERS, "if-match": created.metaEtag },
        data: { slug: seed.slug, summary: seed.summary },
      }),
    );
  }
  if (seed.body !== undefined) {
    await must(
      await request.put(`${API_ORIGIN}/posts/${id}/body`, {
        headers: { ...HEADERS, "if-match": created.bodyEtag },
        data: { body: seed.body },
      }),
    );
  }
  return { postId: id };
}

async function stored(request: APIRequestContext, id: string): Promise<{ title: string; body: string }> {
  return (await must(await request.get(`${API_ORIGIN}/posts/${id}`))).json();
}

test("creating a post opens its editor and the API holds the title", async ({ page, request }) => {
  const title = unique("First post");
  await page.goto("/");
  await page.getByLabel("Title").fill(title);
  await page.getByRole("button", { name: "Create post" }).click();
  await expect(page).toHaveURL(/\/posts\/[A-Za-z0-9_-]+$/);
  await expect(page.getByLabel("Title")).toHaveValue(title);
  const id = new URL(page.url()).pathname.split("/").pop() as string;
  expect((await stored(request, id)).title).toBe(title);
});

test("typing in the editor autosaves the text through the real ETag flow", async ({ page, request }) => {
  const { postId } = await createPost(request, { title: unique("Typing") });
  await page.goto(`/posts/${postId}`);
  await page.locator(".milkdown .ProseMirror").click();
  await page.keyboard.type("Hello from the browser");
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  await expect.poll(async () => (await stored(request, postId)).body).toContain("Hello from the browser");
});

test("the Preview shows a table with a grid and a boxed code block", async ({ page, request }) => {
  const body = "| a | b |\n| - | - |\n| 1 | 2 |\n\n```python\nprint(1)\n```\n";
  const { postId } = await createPost(request, { title: unique("Table"), body });
  await page.goto(`/posts/${postId}`);
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.locator(".preview th").first()).toHaveCSS("font-weight", "700");
  await expect(page.locator(".preview th").first()).toHaveCSS("background-color", "rgb(238, 238, 238)");
  await expect(page.locator(".preview td").first()).toHaveCSS("border-top-width", "1px");
  await expect(page.locator(".preview pre")).toHaveCSS("overflow-x", "auto");
});
