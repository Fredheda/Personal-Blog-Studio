import type { ApiError } from "../lib/problem";

export const SESSION_MESSAGE =
  "Could not reach the studio. Your session may have expired: reload the page to sign in again.";

/** An API failure for the owner: the validator's problems as a list, each with
 *  its line; a failed fetch (status 0: no answer, or the sign-in redirect that
 *  the browser blocks) says the session may have expired. */
export function ProblemList({ error }: { error: ApiError | null }) {
  if (!error) return null;
  if (error.status === 0) {
    return <p role="alert" className="problem">{SESSION_MESSAGE}</p>;
  }
  const problem = error.problem ?? {
    type: "",
    title: `The request failed (HTTP ${error.status})`,
    status: error.status,
  };
  const lines = problem.problems ?? [];
  return (
    <div role="alert" className="problem">
      <strong>{problem.title}</strong>
      {/* The API's reason (for example "origin not allowed"). A refused body
          lists its problems below instead, where the detail would only repeat them. */}
      {lines.length === 0 && problem.detail && <> {problem.detail}</>}
      {lines.length > 0 && (
        <ul>
          {lines.map((p, i) => (
            <li key={i}>{p.line > 0 ? `Line ${p.line}: ` : ""}{p.message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
