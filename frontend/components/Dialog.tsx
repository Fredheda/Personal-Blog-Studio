"use client";

import { useId, useRef, type ReactNode } from "react";

import { Button } from "./Button";
import { useModal } from "./useModal";

type Props = {
  title: string;
  children: ReactNode;
  cancelLabel: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
};

/** A modal question (spec 7.7): a panel on `pane`, the cautious action on the
 *  left and the default action, white, on the right. Esc, a click on the
 *  backdrop and the cautious button all call `onCancel`. Focus starts on the
 *  cautious button, stays inside, and returns to where it was (`useModal`). */
export function Dialog({ title, children, cancelLabel, confirmLabel, onCancel, onConfirm }: Props) {
  const titleId = useId();
  const textId = useId();
  const cancel = useRef<HTMLButtonElement>(null);
  const { panel, onKeyDown } = useModal(onCancel, cancel);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-deep/70 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={textId}
        onKeyDown={onKeyDown}
        className="w-full max-w-md rounded-2xl border border-line bg-pane p-6 shadow-[0_16px_48px_rgba(0,0,0,0.6)]"
      >
        <h2 id={titleId} className="m-0 text-lg font-semibold text-text">
          {title}
        </h2>
        <div id={textId} className="mt-2 text-muted">{children}</div>
        <div className="mt-5 flex justify-end gap-2">
          <Button ref={cancel} className="m-0" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant="primary" className="m-0" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
