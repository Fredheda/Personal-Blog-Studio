import type { ReactNode } from "react";

import type { Marker, StepView } from "../lib/steps";
import type { CheckProblem } from "../lib/studio-api";

const MARKER: Record<Marker, string> = {
  done: "border-ok bg-ok",
  active: "border-primary",
  attention: "border-warn",
  failed: "border-err",
  waiting: "border-muted",
};

type Props = {
  write: StepView;
  check: StepView & { problems: CheckProblem[] };
  publish: StepView & { canUnpublish: boolean };
  onUnpublish: () => void;
};

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

function Step({ n, name, view, children }: { n: number; name: string; view: StepView; children?: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        aria-hidden
        data-marker={view.marker}
        className={`mt-0.5 size-4 shrink-0 rounded-full border-2 ${MARKER[view.marker]}`}
      />
      <div className="min-w-0">
        <div className="font-semibold text-text">
          {n} {name}
        </div>
        <p className="m-0 text-muted">{view.text}</p>
        {children}
      </div>
    </li>
  );
}

/** The numbered steps of a post (spec 7.5): Write, Check, Publish. */
export function StepsLane({ write, check, publish, onUnpublish }: Props) {
  return (
    <ol aria-label="Steps" className="m-0 list-none space-y-5 p-0">
      <Step n={1} name="Write" view={write} />
      <Step n={2} name="Check" view={check}>
        {check.problems.length > 0 && (
          <ul className="m-0 mt-2 list-none space-y-1.5 p-0">
            {check.problems.map((problem, i) => (
              <li key={i} className="rounded-lg border border-line bg-pane px-2.5 py-1.5">
                {problem.line > 0 && <span className="text-warn">Line {problem.line}</span>}
                {problem.line > 0 ? ` ${problem.message}` : capital(problem.message)}
              </li>
            ))}
          </ul>
        )}
      </Step>
      <Step n={3} name="Publish" view={publish}>
        {publish.canUnpublish && (
          <button
            type="button"
            className="m-0 border-0 bg-transparent p-0 text-text underline underline-offset-2"
            onClick={onUnpublish}
          >
            Unpublish
          </button>
        )}
      </Step>
    </ol>
  );
}
