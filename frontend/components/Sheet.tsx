"use client";

import { useId, useRef, type ReactNode } from "react";

import { Button } from "./Button";
import { useModal } from "./useModal";

export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const titleId = useId();
  const close = useRef<HTMLButtonElement>(null);
  const { panel, onKeyDown } = useModal(onClose, close);
  return (
    <div
      className="fixed inset-0 z-50 bg-deep/70"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
        className="absolute inset-x-0 bottom-0 max-h-[70vh] overflow-y-auto rounded-t-2xl border border-line bg-pane p-4"
      >
        <div className="flex items-center justify-between gap-3">
          <h2 id={titleId} className="m-0 text-lg font-semibold text-text">
            {title}
          </h2>
          <Button ref={close} className="m-0" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="mt-3">{children}</div>
      </div>
    </div>
  );
}
