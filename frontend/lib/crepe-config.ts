import { languages } from "@codemirror/language-data";
import { Crepe } from "@milkdown/crepe";

import { matlab } from "./matlab";

export const crepeFeatures = {
  [Crepe.Feature.ImageBlock]: false, // media arrives with BLOG-19
  [Crepe.Feature.AI]: false,
};

export const crepeFeatureConfigs = {
  [Crepe.Feature.Latex]: {
    // MathML only: no KaTeX CSS, no maths font (owner rule).
    katexOptions: { output: "mathml" as const, throwOnError: false },
  },
  [Crepe.Feature.CodeMirror]: {
    languages: [matlab, ...languages],
  },
  [Crepe.Feature.Placeholder]: {
    text: "Write your post. Type / for blocks.",
  },
};
