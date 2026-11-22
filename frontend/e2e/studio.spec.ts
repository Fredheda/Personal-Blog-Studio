import { expect, test, type APIRequestContext, type APIResponse, type Page } from "@playwright/test";

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
  await expect(page.getByRole("banner").getByText(/^Saved/)).toBeVisible();
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

test("the editor is dark, shares the Preview's type and colours code with the token colours", async ({ page, request }) => {
  const body = "## Heading\n\n#### Small\n\n- one\n- two\n\n```Python\ndef f():\n    return 1\n```\n";
  const { postId } = await createPost(request, { title: unique("Editor"), body });
  await page.goto(`/posts/${postId}`);
  await expect(page.locator(".crepe-host .milkdown")).toHaveCSS("background-color", "rgb(16, 18, 23)");
  await expect(page.locator(".milkdown .ProseMirror h2")).toHaveCSS("font-size", "21.78px");
  await expect(page.locator(".milkdown .ProseMirror h4")).toHaveCSS("font-size", "16.5px");
  await expect(page.locator(".milkdown .label-wrapper").first()).toBeVisible();
  await expect(page.locator(".milkdown .label-wrapper").first()).toHaveCSS("color", "rgb(152, 161, 179)");
  const block = page.locator(".milkdown .milkdown-code-block").first();
  await block.scrollIntoViewIfNeeded();
  await expect(block.locator(".cm-editor")).toHaveCSS("background-color", "rgb(11, 13, 17)");
  await expect(block.locator(".cm-content span", { hasText: "def" }).first()).toHaveCSS("color", "rgb(185, 168, 255)");
});

test("publishing shows a green status strip", async ({ page, request }) => {
  const slug = `strip-${Math.random().toString(36).slice(2, 8)}`;
  const { postId } = await createPost(request, { title: unique("Strip"), slug, summary: "Sum", body: "Hello." });
  await page.goto(`/posts/${postId}`);
  await page.getByRole("button", { name: "Publish", exact: true }).click();
  const strip = page.locator('[role="status"]', { hasText: "Published as version 1" });
  await expect(strip).toBeVisible();
  await expect(strip).toHaveCSS("border-top-color", "rgb(95, 227, 161)");
  await expect(strip).toHaveCSS("border-top-left-radius", "12px");
});

test("Delete asks in a dialog: once for a draft or a post that is live, twice for a post published earlier", async ({ page, request }) => {
  const draftTitle = unique("Doomed draft");
  const liveTitle = unique("Doomed live");
  const onceTitle = unique("Doomed once");
  const slug = () => `del-${Math.random().toString(36).slice(2, 8)}`;
  const draft = await createPost(request, { title: draftTitle });
  const live = await createPost(request, { title: liveTitle, slug: slug(), summary: "Sum", body: "Hello.", publish: true });
  const once = await createPost(request, { title: onceTitle, slug: slug(), summary: "Sum", body: "Hello.", publish: true });
  await must(await request.post(`${API_ORIGIN}/posts/${once.postId}/unpublish`, { headers: HEADERS }));
  await page.goto("/");

  await page.getByRole("button", { name: `Delete ${draftTitle}` }).click();
  await expect(page.getByRole("dialog", { name: "Delete this draft?" })).toBeVisible();
  const backdrop = page.getByRole("dialog").locator("xpath=..");
  await expect(backdrop).not.toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("link", { name: draftTitle })).toHaveCount(1);
  await page.getByRole("button", { name: `Delete ${draftTitle}` }).click();
  await page.getByRole("button", { name: "Delete draft" }).click();
  await expect(page.getByRole("link", { name: draftTitle })).toHaveCount(0);
  expect((await request.get(`${API_ORIGIN}/posts/${draft.postId}`)).status()).toBe(404);

  await page.getByRole("button", { name: `Delete ${liveTitle}` }).click();
  await expect(page.getByRole("dialog", { name: "Delete this post?" })).toBeVisible();
  await page.getByRole("button", { name: "Delete post" }).click();
  await expect(page.getByRole("link", { name: liveTitle })).toHaveCount(0);
  expect((await request.get(`${API_ORIGIN}/posts/${live.postId}`)).status()).toBe(404);

  await page.getByRole("button", { name: `Delete ${onceTitle}` }).click();
  await page.getByRole("button", { name: "Delete draft" }).click();
  await expect(page.getByRole("dialog", { name: "Delete this post?" })).toBeVisible();
  await page.getByRole("button", { name: "Delete post" }).click();
  await expect(page.getByRole("link", { name: onceTitle })).toHaveCount(0);
  expect((await request.get(`${API_ORIGIN}/posts/${once.postId}`)).status()).toBe(404);
});

test("the list shows draft and published pills and the white primary button", async ({ page, request }) => {
  const title = unique("Pills");
  await createPost(request, { title, slug: `pill-${Math.random().toString(36).slice(2, 8)}`, summary: "Sum", body: "Hello.", publish: true });
  await page.goto("/");
  const row = page.locator("li", { hasText: title });
  await expect(row.getByText("Published, version 1")).toBeVisible();
  await expect(row.locator(".bg-ok")).toHaveCSS("background-color", "rgb(95, 227, 161)");
  await page.getByLabel("Title").fill("x");
  await expect(page.getByRole("button", { name: "Create post" })).toHaveCSS("background-color", "rgb(255, 255, 255)");
});

const RAW_HTML_BODY = "# Title\n\nText.\n\n<div>raw</div>\n";
const slugFor = (label: string) => `${label}-${Math.random().toString(36).slice(2, 8)}`;

test("a post with a problem shows it under Check, keeps Publish off, and publishes once it is fixed", async ({ page, request }) => {
  const { postId } = await createPost(request, {
    title: unique("Fix"),
    slug: slugFor("fix"),
    summary: "A summary.",
    body: RAW_HTML_BODY,
  });
  await page.goto(`/posts/${postId}`);
  const lane = page.getByRole("complementary", { name: "Post steps" });
  await expect(lane.getByText(/to fix before publishing/)).toBeVisible();
  await expect(lane.getByText(/^Line \d+/)).toBeVisible();
  const publish = page.getByRole("banner").getByRole("button", { name: "Publish" });
  await expect(publish).toBeDisabled();
  await expect(publish).toHaveAttribute("title", "Fix the problems under Check first");

  await page.locator(".milkdown .ProseMirror").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("Plain text now");
  await expect(lane.getByText("No problems found")).toBeVisible();
  await expect(publish).toBeEnabled();
  await publish.click();
  await expect(page.getByRole("status").filter({ hasText: /^Published as version 1/ })).toBeVisible();
  await expect(lane.getByText(/^Published, version 1, on /)).toBeVisible();
});

test("Unpublish asks in a dialog from the Publish step, and unpublishes on the answer", async ({ page, request }) => {
  const { postId } = await createPost(request, {
    title: unique("Live"),
    slug: slugFor("live"),
    summary: "A summary.",
    body: "Hello.",
    publish: true,
  });
  await page.goto(`/posts/${postId}`);
  const lane = page.getByRole("complementary", { name: "Post steps" });
  await lane.getByRole("button", { name: "Unpublish" }).click();
  await expect(page.getByRole("dialog", { name: "Unpublish this post?" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(lane.getByText(/^Published, version 1/)).toBeVisible();
  await lane.getByRole("button", { name: "Unpublish" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Unpublish" }).click();
  await expect(page.getByText(/^Unpublished\./)).toBeVisible();
  await expect(lane.getByText(/^Not published yet/)).toBeVisible();
});

test("a change made elsewhere shows the conflict strip and turns Save and Publish off", async ({ page, request }) => {
  const { postId } = await createPost(request, { title: unique("Clash"), body: "One." });
  await page.goto(`/posts/${postId}`);
  await expect(page.getByRole("banner").getByText(/^Saved/)).toBeVisible();
  const current = await (await must(await request.get(`${API_ORIGIN}/posts/${postId}`))).json();
  await must(
    await request.put(`${API_ORIGIN}/posts/${postId}/body`, {
      headers: { ...HEADERS, "if-match": current.bodyEtag },
      data: { body: "Changed elsewhere." },
    }),
  );
  await page.locator(".milkdown .ProseMirror").click();
  await page.keyboard.type(" more");
  await expect(page.getByRole("alert").filter({ hasText: "This post changed elsewhere" })).toBeVisible();
  await expect(page.getByRole("banner").getByText("Not saved: the post changed elsewhere")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Publish" })).toBeDisabled();
});

test("on a wide screen the lane is a 262px column beside the page; Preview toggles in the top bar", async ({ page, request }) => {
  const { postId } = await createPost(request, { title: unique("Layout"), body: "# Heading\n\nText." });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/posts/${postId}`);
  const lane = page.getByRole("complementary", { name: "Post steps" });
  await expect(lane).toHaveCSS("width", "262px");
  const preview = page.getByRole("banner").getByRole("button", { name: "Preview" });
  await preview.click();
  await expect(preview).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".post-body h1")).toHaveText("Heading");
  await preview.click();
  await expect(page.locator(".milkdown .ProseMirror")).toBeVisible();
});

test("on a long post the top bar and the steps stay in view at the end of the page", async ({ page, request }) => {
  const body = Array.from({ length: 120 }, (_, i) => `Paragraph ${i + 1}.`).join("\n\n");
  const { postId } = await createPost(request, { title: unique("Long"), body });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/posts/${postId}`);
  await expect(page.locator(".milkdown .ProseMirror")).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(page.getByText("Paragraph 120.")).toBeInViewport();
  await expect(page.getByRole("banner").getByRole("button", { name: "Publish" })).toBeInViewport();
  await expect(page.getByRole("complementary", { name: "Post steps" }).getByText("1 Write")).toBeInViewport();
});

test("on a phone Preview and Save sit in a bottom bar and the steps are chips", async ({ page, request }) => {
  const { postId } = await createPost(request, { title: unique("Phone"), body: "Text." });
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto(`/posts/${postId}`);
  const box = await page.getByRole("button", { name: "Save", exact: true }).boundingBox();
  expect(box !== null && box.y > 700).toBeTruthy();
  await expect(page.getByRole("complementary", { name: "Post steps" })).toBeHidden();
  await expect(page.getByRole("group", { name: "Steps summary" })).toBeVisible();
});

const FAR_HTML_BODY = `# Title\n\n${Array.from({ length: 60 }, (_, i) => `Paragraph ${i + 1}.`).join("\n\n")}\n\n<div>raw</div>\n`;

async function caretBlockText(page: Page) {
  return page.evaluate(() => {
    const node = document.getSelection()?.anchorNode;
    const element = node instanceof Element ? node : node?.parentElement;
    return element?.closest("p")?.textContent ?? "";
  });
}

test("a click on a problem in the lane moves the caret to its block, and typing lands there", async ({ page, request }) => {
  const { postId } = await createPost(request, {
    title: unique("Jump"),
    slug: slugFor("jump"),
    summary: "A summary.",
    body: FAR_HTML_BODY,
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/posts/${postId}`);
  const lane = page.getByRole("complementary", { name: "Post steps" });
  await lane.getByRole("button", { name: /^Line \d+/ }).click();
  const block = page.locator(".milkdown .ProseMirror p", { hasText: "raw" });
  await expect(block).toBeInViewport();
  expect(await caretBlockText(page)).toContain("raw");
  await page.keyboard.type("Z");
  await expect(block).toContainText("Z");
});

test("on a phone the Check chip opens the problems and a tap on one jumps to its line; the strip stays in view", async ({ page, request }) => {
  const { postId } = await createPost(request, {
    title: unique("Phone jump"),
    slug: slugFor("pj"),
    summary: "A summary.",
    body: FAR_HTML_BODY,
  });
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto(`/posts/${postId}`);
  const chips = page.getByRole("group", { name: "Steps summary" });
  await expect(chips.getByText(/^1 Saved/)).toBeVisible();
  await expect(chips.getByText(/^3 Not published/)).toBeVisible();
  await chips.getByRole("button", { name: /to fix/ }).click();
  await page.getByRole("dialog", { name: "Check" }).getByRole("button", { name: /^Line \d+/ }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".milkdown .ProseMirror p", { hasText: "raw" })).toBeInViewport();
  expect(await caretBlockText(page)).toContain("raw");
  await expect(chips).toBeInViewport();
});

test("on a phone the Publish chip opens the Publish step and Unpublish asks first", async ({ page, request }) => {
  const { postId } = await createPost(request, {
    title: unique("Phone live"),
    slug: slugFor("pl"),
    summary: "A summary.",
    body: "Hello.",
    publish: true,
  });
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto(`/posts/${postId}`);
  await page.getByRole("group", { name: "Steps summary" }).getByRole("button", { name: /^3 Published/ }).click();
  const sheet = page.getByRole("dialog", { name: "Publish" });
  await expect(sheet.getByText(/^Published, version 1/)).toBeVisible();
  await sheet.getByRole("button", { name: "Unpublish" }).click();
  await expect(page.getByRole("dialog", { name: "Unpublish this post?" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Publish", exact: true })).toBeVisible();
});
