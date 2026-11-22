import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkParse from "remark-parse";
import { unified } from "unified";

const parser = unified().use(remarkParse).use(remarkGfm).use(remarkMath);

export function blockStartLines(markdown: string): number[] {
  return parser
    .parse(markdown)
    .children.filter((node) => node.type !== "definition")
    .map((node) => node.position?.start.line ?? 0);
}

export function jumpTarget(markdown: string, line: number, blockCount: number): number | null {
  if (line < 1) return null;
  const starts = blockStartLines(markdown);
  if (starts.length === 0 || blockCount < starts.length || blockCount > starts.length + 1) return null;
  let index = 0;
  starts.forEach((start, i) => {
    if (start <= line) index = i;
  });
  return index;
}
