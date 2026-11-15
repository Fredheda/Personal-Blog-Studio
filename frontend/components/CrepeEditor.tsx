"use client";

// The theme's own `common/style.css` also pulls in `common/latex.css`, which
// imports KaTeX's stylesheet and with it eight font families. Maths is MathML
// only here, so the parts are imported one by one, without latex.css, and the
// two rules the maths editing popup needs live in app/globals.css.
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
import "@milkdown/crepe/theme/classic.css";

import { Crepe } from "@milkdown/crepe";
import { useEffect, useRef } from "react";

import { crepeFeatureConfigs, crepeFeatures } from "../lib/crepe-config";
import { normaliseMarkdown } from "../lib/normalise";

type Props = {
  initial: string;
  onChange: (markdown: string) => void;
  readonly?: boolean;
};

/** Milkdown Crepe as a Markdown editor. `initial` is read once, at mount: the
 *  parent remounts it with a new `key` to replace the text (reload). Nothing is
 *  reported until the owner changes the text: whatever Crepe makes of the loaded
 *  Markdown is taken as the baseline, so opening a post never writes it. */
export function CrepeEditor({ initial, onChange, readonly = false }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const latestOnChange = useRef(onChange);
  useEffect(() => {
    latestOnChange.current = onChange;
  });

  useEffect(() => {
    const root = host.current;
    if (root === null) return;
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
      crepe.setReadonly(readonly);
      ready = true;
    });
    return () => {
      alive = false;
      void crepe.destroy();
    };
    // `initial` and `readonly` are mount-time inputs by design.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={host} className="crepe-host" />;
}
