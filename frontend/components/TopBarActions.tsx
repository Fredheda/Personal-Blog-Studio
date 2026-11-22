"use client";

import { SAVE_DOT, saveText, type SaveKind } from "../lib/steps";
import { Button } from "./Button";

type Props = {
  kind: SaveKind;
  ago: string;
  previewOn: boolean;
  onPreview: () => void;
  canSave: boolean;
  onSave: () => void;
  publish: { enabled: boolean; title?: string };
  onPublish: () => void;
};

/** The right end of the top bar on a post page (spec 7.3): save state, Preview,
 *  Save, Publish. Up to 760px the save state hides and Preview and Save form a
 *  fixed bottom bar (one set of buttons, moved by CSS only). */
export function TopBarActions({ kind, ago, previewOn, onPreview, canSave, onSave, publish, onPublish }: Props) {
  return (
    <div className="flex items-center gap-3">
      <p role="status" className="m-0 hidden items-center gap-2 text-muted min-[760px]:flex">
        <span aria-hidden className={`size-2 rounded-full ${SAVE_DOT[kind]}`} />
        {saveText(kind, ago)}
      </p>
      <div className="max-[760px]:fixed max-[760px]:inset-x-0 max-[760px]:bottom-0 max-[760px]:z-40 max-[760px]:flex max-[760px]:justify-end max-[760px]:gap-2 max-[760px]:border-t max-[760px]:border-line max-[760px]:bg-deep max-[760px]:p-3 min-[760px]:contents">
        <Button className="m-0" aria-pressed={previewOn} onClick={onPreview}>
          Preview
        </Button>
        <Button
          className={`m-0 ${canSave ? "border-primary" : ""}`}
          disabled={!canSave}
          title={canSave ? undefined : "Nothing to save"}
          onClick={onSave}
        >
          Save
        </Button>
      </div>
      <Button variant="primary" className="m-0" disabled={!publish.enabled} title={publish.title} onClick={onPublish}>
        Publish
      </Button>
    </div>
  );
}
