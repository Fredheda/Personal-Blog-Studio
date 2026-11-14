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
): Response {
  return new Response(JSON.stringify({ type: "about:blank", title, status }), {
    status,
    headers: { "content-type": "application/problem+json", "cache-control": "no-store", ...headers },
  });
}
