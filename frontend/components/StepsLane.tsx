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
  onJump?: (line: number) => void;
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

export function Problems({ problems, onJump }: { problems: CheckProblem[]; onJump?: (line: number) => void }) {
  return (
    <ul className="m-0 mt-2 list-none space-y-1.5 p-0">
      {problems.map((problem, i) => {
        const text = (
          <>
            {problem.line > 0 && <span className="text-warn">Line {problem.line}</span>}
            {problem.line > 0 ? ` ${problem.message}` : capital(problem.message)}
          </>
        );
        const card = "rounded-lg border border-line bg-pane px-2.5 py-1.5";
        return (
          <li key={i}>
            {onJump && problem.line > 0 ? (
              <button type="button" className={`m-0 block w-full text-left ${card}`} onClick={() => onJump(problem.line)}>
                {text}
              </button>
            ) : (
              <div className={card}>{text}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function StepsLane({ write, check, publish, onUnpublish, onJump }: Props) {
  return (
    <ol aria-label="Steps" className="m-0 list-none space-y-5 p-0">
      <Step n={1} name="Write" view={write} />
      <Step n={2} name="Check" view={check}>
        {check.problems.length > 0 && <Problems problems={check.problems} onJump={onJump} />}
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

function Chip({ n, view, onOpen }: { n: number; view: StepView; onOpen?: () => void }) {
  const look =
    "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-line bg-pane px-2.5 py-1 text-[12.5px] text-text";
  const body = (
    <>
      <span aria-hidden data-marker={view.marker} className={`size-2.5 rounded-full border-2 ${MARKER[view.marker]}`} />
      {n} {view.chip}
    </>
  );
  return onOpen ? (
    <button type="button" aria-haspopup="dialog" className={`m-0 ${look}`} onClick={onOpen}>
      {body}
    </button>
  ) : (
    <span className={look}>{body}</span>
  );
}

export function StepChips({
  write,
  check,
  publish,
  onOpenProblems,
  onOpenPublish,
}: {
  write: StepView;
  check: StepView & { problems: CheckProblem[] };
  publish: StepView;
  onOpenProblems: () => void;
  onOpenPublish: () => void;
}) {
  return (
    <div
      role="group"
      aria-label="Steps summary"
      className="sticky top-[58px] z-20 flex gap-1.5 overflow-x-auto border-b border-line bg-deep px-3.5 py-2.5 min-[760px]:hidden"
    >
      <Chip n={1} view={write} />
      <Chip n={2} view={check} onOpen={check.problems.length > 0 ? onOpenProblems : undefined} />
      <Chip n={3} view={publish} onOpen={onOpenPublish} />
    </div>
  );
}
