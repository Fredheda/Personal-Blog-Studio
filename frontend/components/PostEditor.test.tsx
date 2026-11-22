import { cleanup, fireEvent, render as renderUi, screen, waitFor, within } from "@testing-library/react";
import { useEffect, type ReactElement } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { ApiError } from "../lib/problem";
import type { Draft, StudioApi } from "../lib/studio-api";
import { PostEditor } from "./PostEditor";
import { TopBar } from "./TopBar";
import { TopBarProvider } from "./TopBarSlot";

vi.mock("next/navigation", () => ({ usePathname: () => "/posts/01AAAAAAAAAAAAAAAAAAAAAAAA" }));

/** The editor puts Save, Publish and the save state into the top bar, so it renders inside one. */
function render(ui: ReactElement) {
  return renderUi(
    <TopBarProvider>
      <TopBar />
      {ui}
    </TopBarProvider>,
  );
}

// The real editor is covered in CrepeEditor.test.tsx; here a textarea stands in.
const jumpToLine = vi.hoisted(() => vi.fn<(line: number, markdown: string) => boolean>(() => true));

vi.mock("./CrepeEditor", () => ({
  CrepeEditor: ({
    initial,
    onChange,
    onReady,
  }: {
    initial: string;
    onChange: (text: string) => void;
    onReady?: (handle: { jumpToLine: (line: number, markdown: string) => boolean } | null) => void;
  }) => {
    useEffect(() => {
      onReady?.({ jumpToLine });
      return () => onReady?.(null);
    }, [onReady]);
    return <textarea aria-label="Body (Markdown)" defaultValue={initial} onChange={(e) => onChange(e.target.value)} />;
  },
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  jumpToLine.mockReset();
  jumpToLine.mockReturnValue(true);
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
  // The check answers with the ETags the saves returned, as the real one does.
  const etags = { bodyEtag: draft.bodyEtag, metaEtag: draft.metaEtag };
  const saveBody = overrides.saveBody;
  const patchMeta = overrides.patchMeta;
  return {
    listPosts: unused,
    createPost: unused,
    getPost: async () => draft,
    saveBody: unused,
    patchMeta: unused,
    publish: unused,
    unpublish: async () => undefined,
    deletePost: unused,
    checkPost: async () => ({ ok: true, problems: [], ...etags }),
    ...overrides,
    ...(saveBody && {
      saveBody: async (...args: Parameters<StudioApi["saveBody"]>) => {
        const answer = await saveBody(...args);
        etags.bodyEtag = answer.bodyEtag;
        return answer;
      },
    }),
    ...(patchMeta && {
      patchMeta: async (...args: Parameters<StudioApi["patchMeta"]>) => {
        const answer = await patchMeta(...args);
        etags.metaEtag = answer.metaEtag;
        return answer;
      },
    }),
  } as StudioApi;
}

const lane = () => screen.getByRole("complementary", { name: "Post steps" });
const loaded = () => screen.findByRole("complementary", { name: "Post steps" });
const bar = () => screen.getByRole("banner");

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
  expect(await within(bar()).findByText(/^Saved /)).toBeTruthy();
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
  expect(await within(bar()).findByText(/^Saved /)).toBeTruthy();
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
  expect((await screen.findByRole("alert")).textContent).toMatch(/changed elsewhere/i);
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
  expect((await screen.findByRole("alert")).textContent).toMatch(/changed elsewhere/i);
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
  expect((await screen.findByRole("alert")).textContent).toMatch(/changed elsewhere/i);
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

const checkAnswer = (problems: { line: number; message: string }[]) => async () => ({
  ok: problems.length === 0,
  problems,
  bodyEtag: draft.bodyEtag,
  metaEtag: draft.metaEtag,
});

test("a loaded post shows its save state in the top bar and in the Write step", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi()} />);
  expect((await within(bar()).findByRole("status")).textContent).toMatch(/^Saved /);
  expect(within(lane()).getByText(/^Saved /)).toBeTruthy();
});

test("the post is checked when it opens and again after each save", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const saveBody = vi.fn(async () => ({ ...draft, bodyEtag: '"b2"', updatedAt: "2026-11-10T10:05:00Z" }));
  const api = fakeApi({ saveBody });
  const checkPost = vi.spyOn(api, "checkPost");
  render(<PostEditor id={draft.postId} api={api} />);
  await loaded();
  await within(lane()).findByText("No problems found");
  expect(checkPost).toHaveBeenCalledTimes(1);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "# New" } });
  await vi.advanceTimersByTimeAsync(1600);
  await waitFor(() => expect(checkPost).toHaveBeenCalledTimes(2));
  await within(lane()).findByText("No problems found");
});

test("Publish waits for the check, with its reason", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi({ checkPost: () => new Promise(() => {}) })} />);
  const publish = await screen.findByRole("button", { name: "Publish" });
  expect((publish as HTMLButtonElement).disabled).toBe(true);
  expect(publish.title).toBe("Checking…");
});

test("Publish is off while the check lists problems, and the lane lists them", async () => {
  const checkPost = checkAnswer([
    { line: 3, message: "raw HTML is not allowed" },
    { line: 0, message: "slug is required" },
  ]);
  render(<PostEditor id={draft.postId} api={fakeApi({ checkPost })} />);
  await loaded();
  expect(await within(lane()).findByText("2 things to fix before publishing")).toBeTruthy();
  expect(within(lane()).getByText("Line 3")).toBeTruthy();
  expect(within(lane()).getByText("Slug is required")).toBeTruthy();
  const publish = publishButton();
  expect(publish.disabled).toBe(true);
  expect(publish.title).toBe("Fix the problems under Check first");
});

test("a publish the server refuses although the check passed shows the amber strip and the refusal under Check", async () => {
  const publish = vi.fn(async () => {
    throw new ApiError(422, {
      type: "about:blank",
      title: "Unprocessable Content",
      status: 422,
      problems: [{ line: 3, message: "raw HTML is not allowed" }],
    });
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ publish })} />);
  const button = await screen.findByRole("button", { name: "Publish" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  expect((await screen.findByRole("alert")).textContent).toBe("Not published: fix the problems listed under Check.");
  expect(within(lane()).getByText("1 thing to fix before publishing")).toBeTruthy();
  expect(within(lane()).getByText("Line 3")).toBeTruthy();
  expect(publishButton().disabled).toBe(true);
  expect(publish).toHaveBeenCalledWith(draft.postId, '"b1"');
});

test("a successful publish says which version went live and the Publish step follows", async () => {
  const publish = vi.fn(async () => ({ postId: draft.postId, slug: "hello", version: 2, publishedAt: "t", updatedAt: "t" }));
  const live = {
    ...draft,
    published: true,
    version: 2,
    publishedAt: "2026-11-12T09:00:00Z",
    versionPublishedAt: "2026-11-12T09:00:00Z",
    slugLocked: true,
  };
  const getPost = vi.fn().mockResolvedValueOnce(draft).mockResolvedValue(live);
  render(<PostEditor id={draft.postId} api={fakeApi({ publish, getPost })} />);
  const button = await screen.findByRole("button", { name: "Publish" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  expect(await screen.findByText("Published as version 2. Live at /blog/hello.")).toBeTruthy();
  expect(
    await within(lane()).findByText("Published, version 2, on 12 Nov. Publish again to send your changes."),
  ).toBeTruthy();
});

test("Unpublish asks first; Esc keeps the post published; the answer unpublishes", async () => {
  const live = {
    ...draft,
    published: true,
    version: 1,
    publishedAt: "2026-11-12T09:00:00Z",
    versionPublishedAt: "2026-11-12T09:00:00Z",
    slugLocked: true,
  };
  const unpublish = vi.fn(async () => undefined);
  const getPost = vi.fn().mockResolvedValueOnce(live).mockResolvedValue(draft);
  render(<PostEditor id={draft.postId} api={fakeApi({ unpublish, getPost })} />);
  await loaded();
  fireEvent.click(await within(lane()).findByRole("button", { name: "Unpublish" }));
  expect(screen.getByRole("dialog", { name: "Unpublish this post?" })).toBeTruthy();
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(unpublish).not.toHaveBeenCalled();
  fireEvent.click(within(lane()).getByRole("button", { name: "Unpublish" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Unpublish" }));
  await waitFor(() => expect(unpublish).toHaveBeenCalledWith(draft.postId));
  expect(await screen.findByText(/^Unpublished\./)).toBeTruthy();
  expect(await within(lane()).findByText(/^Not published yet/)).toBeTruthy();
});

test("a green strip goes away with the next edit", async () => {
  const publish = vi.fn(async () => ({ postId: draft.postId, slug: "hello", version: 1, publishedAt: "t", updatedAt: "t" }));
  render(<PostEditor id={draft.postId} api={fakeApi({ publish })} />);
  const button = await screen.findByRole("button", { name: "Publish" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  await screen.findByText(/^Published as version 1/);
  fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Hello again" } });
  expect(screen.queryByText(/^Published as version 1/)).toBeNull();
});

test("with a conflict Save and Publish stay off and the Write step says the post changed elsewhere", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const saveBody = vi.fn(async () => {
    throw problem(412, "Precondition Failed");
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ saveBody })} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "typed" } });
  await vi.advanceTimersByTimeAsync(1600);
  expect(await within(lane()).findByText("Not saved: the post changed elsewhere.")).toBeTruthy();
  expect(saveButton().disabled).toBe(true);
  expect(publishButton().disabled).toBe(true);
});

test("after Save of only the details the post is checked again", async () => {
  const patchMeta = vi.fn(async () => ({
    ...draft,
    title: "Hello again",
    metaEtag: '"m2"',
    updatedAt: "2026-11-10T10:06:00Z",
  }));
  const api = fakeApi({ patchMeta });
  const checkPost = vi.spyOn(api, "checkPost");
  render(<PostEditor id={draft.postId} api={api} />);
  await loaded();
  await within(lane()).findByText("No problems found");
  fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Hello again" } });
  fireEvent.click(saveButton());
  await waitFor(() => expect(checkPost).toHaveBeenCalledTimes(2));
  await within(lane()).findByText("No problems found");
});

test("the refusal's problems go away with the next save", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const publish = vi.fn(async () => {
    throw new ApiError(422, {
      type: "about:blank",
      title: "Unprocessable Content",
      status: 422,
      problems: [{ line: 3, message: "raw HTML is not allowed" }],
    });
  });
  const saveBody = vi.fn(async () => ({ ...draft, bodyEtag: '"b2"', updatedAt: "2026-11-10T10:05:00Z" }));
  render(<PostEditor id={draft.postId} api={fakeApi({ publish, saveBody })} />);
  const button = await screen.findByRole("button", { name: "Publish" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  await within(lane()).findByText("Line 3");
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "# Fixed" } });
  await vi.advanceTimersByTimeAsync(1600);
  await within(lane()).findByText("No problems found");
  expect(within(lane()).queryByText("Line 3")).toBeNull();
});

test("after Reload the post the old answer is gone and the new post is checked", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const checkPost = vi
    .fn<StudioApi["checkPost"]>()
    .mockResolvedValueOnce({
      ok: false,
      problems: [{ line: 3, message: "old problem" }],
      bodyEtag: draft.bodyEtag,
      metaEtag: draft.metaEtag,
    })
    .mockReturnValue(new Promise(() => {}));
  const saveBody = vi.fn(async () => {
    throw problem(412, "Precondition Failed");
  });
  render(<PostEditor id={draft.postId} api={fakeApi({ checkPost, saveBody })} />);
  await loaded();
  await within(lane()).findByText("Line 3");
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "typed" } });
  await vi.advanceTimersByTimeAsync(1600);
  fireEvent.click(await screen.findByRole("button", { name: "Reload the post" }));
  await waitFor(() => expect(within(lane()).queryByText("Line 3")).toBeNull());
  await waitFor(() => expect(within(lane()).getByText("Checking…")).toBeTruthy());
  expect(checkPost).toHaveBeenCalledTimes(2);
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

test("Preview is a toggle that renders the typed Markdown, maths as MathML, and keeps the editor text", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi()} />);
  fireEvent.change(await screen.findByLabelText("Body (Markdown)"), { target: { value: "# Big\n\n$a^2$" } });
  const toggle = screen.getByRole("button", { name: "Preview" });
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-pressed")).toBe("true");
  expect(document.querySelector(".post-body h1")?.textContent).toBe("Big");
  expect(document.querySelectorAll(".post-body math").length).toBeGreaterThan(0);
  fireEvent.click(toggle);
  expect((screen.getByLabelText("Body (Markdown)") as HTMLTextAreaElement).value).toBe("# Big\n\n$a^2$");
});

const rawHtml = checkAnswer([
  { line: 3, message: "raw HTML is not allowed" },
  { line: 0, message: "slug is required" },
]);
const strip = () => screen.getByRole("group", { name: "Steps summary" });
const live = {
  ...draft,
  published: true,
  version: 1,
  publishedAt: "2026-11-12T09:00:00Z",
  versionPublishedAt: "2026-11-12T09:00:00Z",
  slugLocked: true,
};

test("a problem card with a line jumps the editor to that line in the saved text; a card without a line is not a button", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi({ checkPost: rawHtml })} />);
  await loaded();
  fireEvent.click(await within(lane()).findByRole("button", { name: /Line 3/ }));
  await waitFor(() => expect(jumpToLine).toHaveBeenCalledWith(3, draft.body));
  expect(within(lane()).queryByRole("button", { name: /Slug is required/ })).toBeNull();
});

test("when the editor cannot find the line the strip says so, and the next edit clears it", async () => {
  jumpToLine.mockReturnValue(false);
  render(<PostEditor id={draft.postId} api={fakeApi({ checkPost: rawHtml })} />);
  await loaded();
  fireEvent.click(await within(lane()).findByRole("button", { name: /Line 3/ }));
  expect((await screen.findByRole("alert")).textContent).toBe("Could not find line 3 in the editor.");
  fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Hello again" } });
  expect(screen.queryByText("Could not find line 3 in the editor.")).toBeNull();
});

test("a jump from the Preview switches back to the editor first", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi({ checkPost: rawHtml })} />);
  await loaded();
  const toggle = screen.getByRole("button", { name: "Preview" });
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(await within(lane()).findByRole("button", { name: /Line 3/ }));
  expect(toggle.getAttribute("aria-pressed")).toBe("false");
  await waitFor(() => expect(jumpToLine).toHaveBeenCalledWith(3, draft.body));
});

test("the chip strip shows the steps; the Check chip opens the problems as a sheet and a tap on one closes it and jumps", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi({ checkPost: rawHtml })} />);
  await loaded();
  await within(strip()).findByRole("button", { name: "2 2 to fix" });
  expect(strip().textContent).toContain("1 Saved");
  expect(strip().textContent).toContain("3 Not published");
  fireEvent.click(within(strip()).getByRole("button", { name: "2 2 to fix" }));
  const sheet = screen.getByRole("dialog", { name: "Check" });
  fireEvent.click(within(sheet).getByRole("button", { name: /Line 3/ }));
  expect(screen.queryByRole("dialog")).toBeNull();
  await waitFor(() => expect(jumpToLine).toHaveBeenCalledWith(3, draft.body));
});

test("Esc closes the problems sheet and leaves the editor alone", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi({ checkPost: rawHtml })} />);
  await loaded();
  fireEvent.click(await within(strip()).findByRole("button", { name: "2 2 to fix" }));
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(jumpToLine).not.toHaveBeenCalled();
});

test("the Publish chip opens a sheet with the Publish step; Unpublish there asks first", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi({ getPost: async () => live })} />);
  await loaded();
  fireEvent.click(await within(strip()).findByRole("button", { name: "3 Published" }));
  const sheet = screen.getByRole("dialog", { name: "Publish" });
  expect(within(sheet).getByText(/^Published, version 1, on 12 Nov/)).toBeTruthy();
  fireEvent.click(within(sheet).getByRole("button", { name: "Unpublish" }));
  expect(screen.queryByRole("dialog", { name: "Publish" })).toBeNull();
  expect(screen.getByRole("dialog", { name: "Unpublish this post?" })).toBeTruthy();
});

test("a post that is not published has no Unpublish in the Publish sheet", async () => {
  render(<PostEditor id={draft.postId} api={fakeApi()} />);
  await loaded();
  fireEvent.click(await within(strip()).findByRole("button", { name: "3 Not published" }));
  const sheet = screen.getByRole("dialog", { name: "Publish" });
  expect(within(sheet).getByText(/^Not published yet/)).toBeTruthy();
  expect(within(sheet).queryByRole("button", { name: "Unpublish" })).toBeNull();
});
