"use client";

import "@milkdown/crepe/theme/common/style.css";
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
  latestOnChange.current = onChange;

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
