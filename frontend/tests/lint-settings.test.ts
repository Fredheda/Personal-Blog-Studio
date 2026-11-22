// @vitest-environment node
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

async function ruleIds(source: string): Promise<string[]> {
  const eslint = new ESLint({ cwd: process.cwd() });
  const [result] = await eslint.lintText(source, { filePath: "lib/sample.ts" });
  return result.messages.map((message) => message.ruleId ?? "");
}

describe("comment lint settings", () => {
  it.each(["// TODO later", "// fixme", "/* XXX */", "// HACK around it"])(
    "reports %s",
    async (comment) => {
      expect(await ruleIds(`${comment}\nexport const a = 1;\n`)).toContain(
        "no-warning-comments",
      );
    },
  );

  it("leaves an ordinary comment to the rules job", async () => {
    expect(await ruleIds("// a constraint\nexport const a = 1;\n")).not.toContain(
      "no-warning-comments",
    );
  });

  it.each(["components/PostEditor.tsx", "lib/proxy.ts", "tests/hardening.test.ts"])(
    "keeps no-warning-comments an error for %s",
    async (path) => {
      const config = await new ESLint({ cwd: process.cwd() }).calculateConfigForFile(path);
      expect(config.rules?.["no-warning-comments"]?.[0]).toBe(2);
    },
  );
});
