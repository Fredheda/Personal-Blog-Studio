import { LanguageDescription, LanguageSupport, StreamLanguage } from "@codemirror/language";

// CodeMirror's language list has no MATLAB. Its Octave mode highlights MATLAB
// well (same syntax for what a blog shows), so MATLAB blocks use it (spec
// section 7 names this fallback).
export const matlab = LanguageDescription.of({
  name: "MATLAB",
  alias: ["matlab", "octave"],
  extensions: ["m"],
  async load() {
    const { octave } = await import("@codemirror/legacy-modes/mode/octave");
    return new LanguageSupport(StreamLanguage.define(octave));
  },
});
