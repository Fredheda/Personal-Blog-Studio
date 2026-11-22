import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const EFFECTS = ["useEffect", "useLayoutEffect", "useInsertionEffect"];
const NO_EFFECTS =
  "No effects in components: use a hook from frontend/effects, or derive the value, use an event handler or a key.";
const NO_REEXPORT = "The effects folder must not re-export from react: export a named hook instead.";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "no-warning-comments": [
        "error",
        { terms: ["todo", "fixme", "xxx", "hack"], location: "anywhere" },
      ],
      "no-restricted-imports": [
        "error",
        { paths: [{ name: "react", importNames: EFFECTS, message: NO_EFFECTS }] },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "MemberExpression[property.name=/^use(Layout|Insertion)?Effect$/]",
          message: NO_EFFECTS,
        },
        {
          selector: "MemberExpression[property.value=/^use(Layout|Insertion)?Effect$/]",
          message: NO_EFFECTS,
        },
        {
          selector: "ObjectPattern > Property[key.name=/^use(Layout|Insertion)?Effect$/]",
          message: NO_EFFECTS,
        },
        {
          selector: "ObjectPattern > Property[key.value=/^use(Layout|Insertion)?Effect$/]",
          message: NO_EFFECTS,
        },
      ],
    },
  },
  {
    files: ["effects/**"],
    rules: {
      "no-restricted-imports": "off",
      "no-restricted-syntax": [
        "error",
        { selector: 'ExportNamedDeclaration[source.value="react"]', message: NO_REEXPORT },
        { selector: 'ExportAllDeclaration[source.value="react"]', message: NO_REEXPORT },
        {
          selector: "ExportSpecifier[local.name=/^use(Layout|Insertion)?Effect$/]",
          message: NO_REEXPORT,
        },
      ],
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);

export default eslintConfig;
