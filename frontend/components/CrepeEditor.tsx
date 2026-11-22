"use client";

// Theme parts are imported one by one: common/latex.css would pull in KaTeX's fonts.
import "@milkdown/crepe/theme/common/prosemirror.css";
import "@milkdown/crepe/theme/common/reset.css";
import "@milkdown/crepe/theme/common/block-edit.css";
import "@milkdown/crepe/theme/common/code-mirror.css";
import "@milkdown/crepe/theme/common/cursor.css";
import "@milkdown/crepe/theme/common/link-tooltip.css";
import "@milkdown/crepe/theme/common/list-item.css";
import "@milkdown/crepe/theme/common/placeholder.css";
import "@milkdown/crepe/theme/common/toolbar.css";
import "@milkdown/crepe/theme/common/table.css";
import "@milkdown/crepe/theme/classic-dark.css";

import { Crepe } from "@milkdown/crepe";

import { useLatest } from "../effects/useLatest";
import { useWidget } from "../effects/useWidget";
import { crepeFeatureConfigs, crepeFeatures } from "../lib/crepe-config";
import { jumpTarget } from "../lib/line-map";
import { normaliseMarkdown } from "../lib/normalise";

export type EditorHandle = { jumpToLine: (line: number, markdown: string) => boolean };

type Props = {
  initial: string;
  onChange: (markdown: string) => void;
  onReady?: (handle: EditorHandle | null) => void;
};

function placeCaret(editor: HTMLElement, block: Element) {
  editor.focus({ preventScroll: true });
  const range = document.createRange();
  range.selectNodeContents(block);
  range.collapse(true);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
  block.scrollIntoView?.({ block: "center" });
}

/** `initial` is read once, at mount; nothing is reported until the text changes. */
export function CrepeEditor({ initial, onChange, onReady }: Props) {
  const latestOnChange = useLatest(onChange);
  const latestOnReady = useLatest(onReady);

  const host = useWidget<HTMLDivElement>((root) => {
    const crepe = new Crepe({
      root,
      defaultValue: initial,
      features: crepeFeatures,
      featureConfigs: crepeFeatureConfigs,
    });
    let ready = false;
    let reported = "";
    crepe.on((listener) => {
      listener.markdownUpdated((_ctx, markdown) => {
        if (!ready) return;
        const text = normaliseMarkdown(markdown);
        if (text === reported) return;
        reported = text;
        latestOnChange.current(text);
      });
    });
    let alive = true;
    void crepe.create().then(() => {
      if (!alive) return void crepe.destroy();
      reported = normaliseMarkdown(crepe.getMarkdown());
      ready = true;
      latestOnReady.current?.({
        jumpToLine(line, markdown) {
          const editor = root.querySelector<HTMLElement>(".ProseMirror");
          if (editor === null) return false;
          const blocks = [...editor.children].filter((c) => !c.classList.contains("ProseMirror-widget"));
          const index = jumpTarget(markdown, line, blocks.length);
          if (index === null) return false;
          placeCaret(editor, blocks[index]);
          return true;
        },
      });
    });
    return () => {
      alive = false;
      latestOnReady.current?.(null);
      void crepe.destroy();
    };
  });

  return <div ref={host} className="crepe-host" />;
}
