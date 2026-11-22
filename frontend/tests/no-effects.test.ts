// @vitest-environment node
import { readdirSync } from "node:fs";
import { join, relative } from "node:path";

import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const SNIPPETS = {
  "a named import": 'import { useEffect } from "react";\nuseEffect(() => {}, []);\n',
  "a renamed import": 'import { useEffect as run } from "react";\nrun(() => {}, []);\n',
  "a member call": 'import React from "react";\nReact.useEffect(() => {}, []);\n',
  "a computed member call": 'import React from "react";\nReact["useLayoutEffect"](() => {}, []);\n',
  "a destructured binding": 'import React from "react";\nconst { useEffect } = React;\nuseEffect(() => {}, []);\n',
  "a renamed destructured binding": 'import React from "react";\nconst { useEffect: run } = React;\nrun(() => {}, []);\n',
  "useLayoutEffect": 'import { useLayoutEffect } from "react";\nuseLayoutEffect(() => {}, []);\n',
  "useInsertionEffect": 'import { useInsertionEffect } from "react";\nuseInsertionEffect(() => {}, []);\n',
};

const RE_EXPORTS = {
  "a named re-export": 'export { useEffect } from "react";\n',
  "a star re-export": 'export * from "react";\n',
};

const eslint = new ESLint({ cwd: process.cwd() });

async function ruleIds(source: string, filePath: string): Promise<string[]> {
  const [result] = await eslint.lintText(source, { filePath });
  return result.messages.map((message) => message.ruleId ?? "");
}

function restricted(ids: string[]): boolean {
  return ids.includes("no-restricted-imports") || ids.includes("no-restricted-syntax");
}

function sources(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (["node_modules", ".next", "effects"].includes(entry.name)) return [];
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

describe("the no-effects rule", () => {
  it.each(Object.entries(SNIPPETS))("rejects %s outside the effects folder", async (_name, source) => {
    expect(restricted(await ruleIds(source, "components/Sample.tsx"))).toBe(true);
  });

  it.each(Object.entries(SNIPPETS))("allows %s inside the effects folder", async (_name, source) => {
    expect(restricted(await ruleIds(source, "effects/useSample.ts"))).toBe(false);
  });

  it.each(Object.entries(RE_EXPORTS))("rejects %s inside the effects folder", async (_name, source) => {
    expect(restricted(await ruleIds(source, "effects/useSample.ts"))).toBe(true);
  });

  it("does not exempt tests or a nested folder of the same name", async () => {
    const source = SNIPPETS["a named import"];
    expect(restricted(await ruleIds(source, "components/Sample.test.tsx"))).toBe(true);
    expect(restricted(await ruleIds(source, "components/effects/useSample.ts"))).toBe(true);
  });

  it("applies both rules at error level to every source file outside the effects folder", async () => {
    const files = sources(process.cwd()).map((path) => relative(process.cwd(), path));
    expect(files.length).toBeGreaterThan(20);
    const ignored: string[] = [];
    for (const file of files) {
      const config = await eslint.calculateConfigForFile(file);
      if (config === undefined) {
        ignored.push(file);
        continue;
      }
      expect(config.rules?.["no-restricted-imports"]?.[0], file).toBe(2);
      expect(config.rules?.["no-restricted-syntax"]?.[0], file).toBe(2);
    }
    expect(ignored.filter((file) => file !== "next-env.d.ts")).toEqual([]);
  });
});
