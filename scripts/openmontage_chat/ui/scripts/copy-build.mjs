import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const source = resolve(import.meta.dirname, "../dist/index.html");
const target = resolve(import.meta.dirname, "../../index.html");
const built = await readFile(source, "utf8");
const script = built.match(/<script type="module"[^>]*>([\s\S]*?)<\/script>/);
if (!script) throw new Error("Vite output did not contain the expected inline module");
const html = built
  .replace(script[0], "")
  .replace("</body>", () => `<script>${script[1]}</script>\n  </body>`)
  .replace(/^[\t ]+$/gm, "");

await writeFile(target, html, "utf8");
