"use client";

import matlab from "highlight.js/lib/languages/matlab";
import { common } from "lowlight";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

/** What the Markdown renders to for a reader: tables, code, maths as MathML.
 *  Raw HTML is skipped (the validator refuses it at publish), the default URL
 *  transform drops javascript: targets, and images are not drawn at all until
 *  media exists (BLOG-19): the alt text stands in, so a remote URL typed into
 *  the Markdown is never fetched. */
export function Preview({ markdown }: { markdown: string }) {
  return (
    <article className="post-body">
      <ReactMarkdown
        skipHtml
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[
          [rehypeKatex, { output: "mathml", throwOnError: false }],
          [rehypeHighlight, { languages: { ...common, matlab }, plainText: ["math", "text", "txt"] }],
        ]}
        components={{ img: ({ alt }) => <em>{alt ?? ""}</em> }}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  );
}
