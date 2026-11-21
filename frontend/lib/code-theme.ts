import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";

// The colours are the CSS variables of app/globals.css (spec 7.1), so the
// editor and the Preview cannot drift apart.
const highlight = HighlightStyle.define([
  { tag: [t.keyword, t.controlKeyword, t.definitionKeyword, t.moduleKeyword, t.operatorKeyword], color: "var(--color-code-keyword)" },
  { tag: [t.function(t.variableName), t.function(t.propertyName), t.definition(t.function(t.variableName)), t.className], color: "var(--color-code-function)" },
  { tag: [t.number, t.integer, t.float, t.bool, t.null], color: "var(--color-code-number)" },
  { tag: [t.comment, t.lineComment, t.blockComment, t.docComment], color: "var(--color-code-comment)" },
]);

/** A dark CodeMirror theme for Crepe's code blocks: the plain code ink, the
 *  caret, the selection and the four token colours. The block's background is
 *  set in app/globals.css: Crepe's own rule on `.cm-editor` is more specific
 *  than anything a CodeMirror theme can say. */
export const studioCodeTheme = [
  EditorView.theme(
    {
      "&": { color: "var(--color-code-ink)" },
      ".cm-content": { caretColor: "var(--color-primary)" },
      ".cm-gutters": { color: "var(--color-muted)", border: "none" },
      ".cm-activeLine, .cm-activeLineGutter": { backgroundColor: "transparent" },
      "&.cm-focused .cm-selectionBackground, .cm-selectionBackground": { backgroundColor: "var(--crepe-color-selected)" },
    },
    { dark: true },
  ),
  syntaxHighlighting(highlight),
];
