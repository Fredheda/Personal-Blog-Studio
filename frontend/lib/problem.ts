export type Problem = {
  type: string;
  title: string;
  status: number;
  detail?: string;
  problems?: { line: number; message: string }[];
  mediaIds?: string[];
};

export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem | null;

  constructor(status: number, problem: Problem | null) {
    super(problem?.title ?? `HTTP ${status}`);
    this.status = status;
    this.problem = problem;
  }
}

/** A problem+json response with fixed text, as the APIs send. */
export function problemResponse(
  status: number,
  title: string,
  headers: Record<string, string> = {},
  detail?: string,
): Response {
  const body = { type: "about:blank", title, status, ...(detail === undefined ? {} : { detail }) };
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/problem+json", "cache-control": "no-store", ...headers },
  });
}
