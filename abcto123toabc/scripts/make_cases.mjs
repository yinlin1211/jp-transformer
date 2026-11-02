// Generate 123 and round-trip ABC for every ABC in data/abc.
// Usage: node scripts/make_cases.mjs [abc-dir]
// Requires DOLCE_CLI (default: ../TENOR/vendor/dolce/out/cli/j123.js).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const SRC = process.argv[2] || path.join(ROOT, "data", "abc");
const DOLCE =
  process.env.DOLCE_CLI ||
  "/mnt/ssd/lian/白马入芦花janpu/TENOR/vendor/dolce/out/cli/j123.js";

const { parseAbc, parse123, emit123, emitAbc } = await import(DOLCE);

/** ABC requires K: to be the last header field; Dolce's emitter also writes
 *  K: before M:/L:. Move it to the end for standards-compliant renderers. */
function fixHeaders(text) {
  const lines = text.split("\n");
  const head = [];
  const body = [];
  let inBody = false;
  for (const line of lines) {
    const isField = /^[A-Za-z]:/.test(line);
    const isComment = line.startsWith("%");
    if (!inBody && (!line.trim() || isField || isComment)) {
      if (line.trim()) head.push(line);
    } else {
      inBody = true;
      body.push(line);
    }
  }
  const key = head.filter((line) => line.startsWith("K:"));
  const rest = head.filter((line) => !line.startsWith("K:"));
  if (!rest.some((line) => line.startsWith("X:"))) rest.unshift("X:1");
  return [...rest, ...key, ...body].join("\n") + "\n";
}

const outDirs = ["alex123", "rt_abc", "direct_abc"].map((name) => {
  const dir = path.join(ROOT, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
});

const files = fs
  .readdirSync(SRC)
  .filter((name) => name.endsWith(".abc"))
  .sort();

let converted = 0;
for (const name of files) {
  const source = fs.readFileSync(path.join(SRC, name), "utf8");
  const stem = name.replace(/\.abc$/, "");
  try {
    const doc = parseAbc(source);
    const text123 = emit123(doc);
    const roundtrip = emitAbc(parse123(text123));
    fs.writeFileSync(path.join(outDirs[0], `${stem}.123`), text123);
    fs.writeFileSync(path.join(outDirs[1], `${stem}.abc`), fixHeaders(roundtrip));
    fs.writeFileSync(path.join(outDirs[2], `${stem}.abc`), source);
    converted++;
  } catch (error) {
    console.error(`FAILED ${name}: ${error}`);
  }
}
console.log(`converted ${converted}/${files.length} files`);
