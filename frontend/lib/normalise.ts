const BREAK = /<br\s*\/?>/gi;

/** Milkdown writes an HTML line break for a hard break and for a break inside a
 *  table cell; the publish validator refuses raw HTML. Outside code fences and
 *  inline code, a break becomes a Markdown backslash break, and inside a table
 *  row a space (a row has no line break in Markdown). */
export function normaliseMarkdown(markdown: string): string {
  let inFence = false;
  return markdown
    .split("\n")
    .map((line) => {
      if (/^\s*(```|~~~)/.test(line)) {
        inFence = !inFence;
        return line;
      }
      if (inFence || !BREAK.test(line)) {
        BREAK.lastIndex = 0;
        return line;
      }
      BREAK.lastIndex = 0;
      // Leave breaks that sit inside inline code alone.
      const parts = line.split(/(`[^`]*`)/);
      const isRow = line.trimStart().startsWith("|");
      // A break that ends the line needs no extra newline: the join adds it.
      const last = parts.length - 1;
      const fixed = parts
        .map((part, i) => {
          if (i % 2 === 1) return part;
          if (isRow) return part.replace(BREAK, " ");
          const body = i === last ? part.replace(/<br\s*\/?>\s*$/i, "\\") : part;
          return body.replace(BREAK, "\\\n");
        })
        .join("");
      return fixed.trim() === "\\" ? "" : fixed;
    })
    .join("\n");
}
