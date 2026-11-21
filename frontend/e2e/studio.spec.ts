import { expect, test, type APIRequestContext, type APIResponse } from "@playwright/test";

import { API_ORIGIN } from "./ports.ts";

// The API behind the web app is the real studio API, so these helpers use its
// real rules: the custom header on every write and the ETag in If-Match.
const HEADERS = { "x-blog-studio": "1" };

type Seed = { title: string; slug?: string; summary?: string; body?: string; publish?: boolean };

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
    const saved = await (
      await must(
        await request.put(`${API_ORIGIN}/posts/${id}/body`, {
          headers: { ...HEADERS, "if-match": created.bodyEtag },
          data: { body: seed.body },
        }),
      )
    ).json();
    if (seed.publish) {
      await must(
        await request.post(`${API_ORIGIN}/posts/${id}/publish`, {
          headers: { ...HEADERS, "if-match": saved.bodyEtag },
        }),
      );
    }
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

test("the studio is dark and its page elements are restyled", async ({ page, request }) => {
  const title = unique("Dark");
  await createPost(request, { title });
  await page.goto("/");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(16, 18, 23)");
  await expect(page.getByRole("heading", { name: "Blog Studio", level: 1 })).toHaveCSS("font-size", "30px");
  await expect(page.getByRole("link", { name: title, exact: true })).toHaveCSS("text-decoration-line", "underline");
});

test("the top bar leads back to the list and marks the current page", async ({ page, request }) => {
  const { postId } = await createPost(request, { title: unique("Bar") });
  await page.goto("/");
  await expect(page.getByRole("link", { name: "All posts", exact: true })).toHaveAttribute("aria-current", "page");
  await page.goto(`/posts/${postId}`);
  await expect(page.getByRole("link", { name: "All posts", exact: true })).not.toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "Studio", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
});

test("the Preview shows headings, lists, links, maths, a table and a boxed code block", async ({ page, request }) => {
  const body =
    "# Big\n\n- one\n- two\n\nA [link](https://example.com) and $a^2$.\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\n```python\nprint(1)\n```\n";
  const { postId } = await createPost(request, { title: unique("Elements"), body });
  await page.goto(`/posts/${postId}`);
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.locator(".post-body h1")).toHaveCSS("font-size", "33px");
  await expect(page.locator(".post-body ul")).toHaveCSS("list-style-type", "disc");
  await expect(page.locator(".post-body a")).toHaveCSS("text-decoration-line", "underline");
  await expect(page.locator(".post-body math")).toHaveCount(1);
  await expect(page.locator(".post-body th").first()).toHaveCSS("font-weight", "600");
  await expect(page.locator(".post-body th").first()).toHaveCSS("background-color", "rgb(32, 36, 45)");
  await expect(page.locator(".post-body td").first()).toHaveCSS("border-top-width", "1px");
  await expect(page.locator(".post-body pre")).toHaveCSS("overflow-x", "auto");
  await expect(page.locator(".post-body pre")).toHaveCSS("background-color", "rgb(11, 13, 17)");
});

test("the Preview colours Python code with the token colours, also for a capital-P fence", async ({ page, request }) => {
  const body = "```Python\ndef f():\n    return True\n\nprint(f(), 1)\n```\n";
  const { postId } = await createPost(request, { title: unique("Code"), body });
  await page.goto(`/posts/${postId}`);
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.locator(".post-body .hljs-keyword").first()).toHaveCSS("color", "rgb(185, 168, 255)");
  await expect(page.locator(".post-body .hljs-literal")).toHaveCSS("color", "rgb(255, 196, 107)");
  await expect(page.locator(".post-body .hljs-number")).toHaveCSS("color", "rgb(255, 196, 107)");
  await expect(page.locator(".post-body .hljs-built_in")).toHaveCSS("color", "rgb(127, 224, 255)");
});

test("Delete removes a draft after one question and a published post after two", async ({ page, request }) => {
  const draftTitle = unique("Doomed draft");
  const liveTitle = unique("Doomed live");
  const draft = await createPost(request, { title: draftTitle });
  const live = await createPost(request, {
    title: liveTitle,
    slug: `live-${Math.random().toString(36).slice(2, 8)}`,
    summary: "Sum",
    body: "Hello.",
    publish: true,
  });
  const questions: string[] = [];
  page.on("dialog", (dialog) => {
    questions.push(dialog.message());
    void dialog.accept();
  });
  await page.goto("/");

  await page.getByRole("button", { name: `Delete ${draftTitle}` }).click();
  await expect(page.getByRole("link", { name: draftTitle })).toHaveCount(0);
  expect(questions).toHaveLength(1);
  expect((await request.get(`${API_ORIGIN}/posts/${draft.postId}`)).status()).toBe(404);

  await page.getByRole("button", { name: `Delete ${liveTitle}` }).click();
  await expect(page.getByRole("link", { name: liveTitle })).toHaveCount(0);
  expect(questions).toHaveLength(3);
  expect(questions[2]).toContain("It was published");
  expect((await request.get(`${API_ORIGIN}/posts/${live.postId}`)).status()).toBe(404);
});
