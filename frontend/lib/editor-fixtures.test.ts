import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { Crepe } from "@milkdown/crepe";
import { afterEach, expect, test } from "vitest";

import { crepeFeatureConfigs, crepeFeatures } from "./crepe-config";
import { normaliseMarkdown } from "./normalise";

const DIR = join(__dirname, "..", "tests", "fixtures", "crepe-output");
let editor: Crepe | undefined;

afterEach(async () => {
  await editor?.destroy();
  document.body.innerHTML = "";
});

async function roundTrip(markdown: string): Promise<string> {
  const root = document.createElement("div");
  document.body.appendChild(root);
  editor = new Crepe({ root, defaultValue: markdown, features: crepeFeatures, featureConfigs: crepeFeatureConfigs });
  await editor.create();
  return normaliseMarkdown(editor.getMarkdown());
}

test.each(readdirSync(DIR).filter((f) => f.endsWith(".md")))(
  "%s is stable: the editor writes back exactly the committed Markdown",
  async (name) => {
    const committed = readFileSync(join(DIR, name), "utf8");
    expect((await roundTrip(committed)).trim()).toBe(committed.trim());
  },
);
