// Fails the build when a font file ended up in the client bundle: a
// dependency's CSS can pull one in without any source file naming it.
import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const FONT = /\.(woff2?|ttf|otf|eot)$/i;

export function findFonts(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return findFonts(path);
    return FONT.test(name) ? [path] : [];
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const found = findFonts(join(process.cwd(), ".next", "static"));
  if (found.length > 0) {
    console.error(`Font files in the build (owner rule: system fonts only):\n${found.join("\n")}`);
    process.exit(1);
  }
  console.log("no font files in .next/static");
}
