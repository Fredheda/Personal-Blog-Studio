import { ApiError, type Problem } from "./problem";

export type ListItem = { postId: string; title: string; slug: string; updatedAt: string };
export type Draft = {
  postId: string;
  title: string;
  slug: string;
  summary: string;
  tags: string[];
  coverMediaId: string | null;
  createdAt: string;
  updatedAt: string;
  body: string;
  bodyEtag: string;
  metaEtag: string;
};
export type MetaPatch = {
  title?: string;
  slug?: string;
  summary?: string;
  tags?: string[];
  coverMediaId?: string;
  clearCover?: boolean;
};
export type Published = {
  postId: string;
  slug: string;
  version: number;
  publishedAt: string;
  updatedAt: string;
};

export type StudioApi = {
  listPosts(): Promise<ListItem[]>;
  createPost(title: string): Promise<Draft>;
  getPost(id: string): Promise<Draft>;
  saveBody(id: string, body: string, ifMatch: string): Promise<Draft>;
  patchMeta(id: string, patch: MetaPatch, ifMatch: string): Promise<Draft>;
  publish(id: string, ifMatch: string): Promise<Published>;
  unpublish(id: string): Promise<void>;
};

const BASE = "/api/studio/posts";

export function createStudioApi(fetchImpl: typeof fetch = (...args) => fetch(...args)): StudioApi {
  async function call<T>(
    method: string,
    path: string,
    options: { body?: unknown; ifMatch?: string } = {},
  ): Promise<T> {
    const headers = new Headers({ "x-blog-studio": "1", accept: "application/json" });
    if (options.body !== undefined) headers.set("content-type", "application/json");
    if (options.ifMatch !== undefined) headers.set("if-match", options.ifMatch);
    let response: Response;
    try {
      response = await fetchImpl(`${BASE}${path}`, {
        method,
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        cache: "no-store",
      });
    } catch {
      // No answer at all: offline, or the expired session's redirect to the
      // sign-in page, which the browser blocks for a fetch. Status 0 is how the
      // UI tells the owner to reload and sign in again.
      throw new ApiError(0, null);
    }
    if (!response.ok) {
      let problem: Problem | null = null;
      try {
        problem = (await response.json()) as Problem;
      } catch {
        problem = null;
      }
      throw new ApiError(response.status, problem);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  return {
    listPosts: async () => (await call<{ items: ListItem[] }>("GET", "")).items,
    createPost: (title) => call("POST", "", { body: { title } }),
    getPost: (id) => call("GET", `/${id}`),
    saveBody: (id, body, ifMatch) => call("PUT", `/${id}/body`, { body: { body }, ifMatch }),
    patchMeta: (id, patch, ifMatch) => call("PATCH", `/${id}/meta`, { body: patch, ifMatch }),
    publish: (id, ifMatch) => call("POST", `/${id}/publish`, { ifMatch }),
    unpublish: (id) => call("POST", `/${id}/unpublish`),
  };
}
