import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const generatedCssPath = resolve(process.cwd(), "src/styles/tailwind.generated.css");
const outputTsPath = resolve(process.cwd(), "src/styles/tailwind-css.ts");

const css = await readFile(generatedCssPath, "utf8");

const content = `export const TAILWIND_CSS = ${JSON.stringify(css)};\n`;
await writeFile(outputTsPath, content, "utf8");
