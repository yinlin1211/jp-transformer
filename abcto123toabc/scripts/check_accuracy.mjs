// Measure ABC -> 123 -> ABC note accuracy, excluding chord stacks.
// Usage: node scripts/check_accuracy.mjs [abc-dir]
// Output: results/accuracy.json

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const SRC = process.argv[2] || path.join(ROOT, "data", "abc");
const DOLCE =
  process.env.DOLCE_CLI ||
  "/mnt/ssd/lian/白马入芦花janpu/TENOR/vendor/dolce/out/cli/j123.js";

const { parseAbc, parse123, emit123, emitAbc, playSourceOf, buildTimeline } =
  await import(DOLCE);

const round = (n) => Math.round(n * 1e9) / 1e9;

function noteEvents(doc) {
  const noteCounts = new Map();
  for (const part of doc.songs[0].parts) {
    for (const measure of part.measures) {
      for (const element of measure.elements) {
        if (element.kind === "chord") noteCounts.set(element.id, element.notes.length);
      }
    }
  }
  return buildTimeline(playSourceOf(doc)).notes.map((note) => ({
    onset: round(note.t0),
    duration: round(note.t1 - note.t0),
    midi: note.pitch,
    sourceChordNotes: noteCounts.get(note.chord?.id) ?? 1,
  }));
}

const sameNote = (a, b) =>
  a.onset === b.onset && a.duration === b.duration && a.midi === b.midi;

const files = fs
  .readdirSync(SRC)
  .filter((name) => name.endsWith(".abc"))
  .sort();

const perFile = {};
let totalNonChord = 0;
let totalExact = 0;
let filesExact = 0;
const filesWithNonChordNotes = [];
const filesWithoutNonChordNotes = [];

for (const name of files) {
  const stem = name.replace(/\.abc$/, "");
  const source = fs.readFileSync(path.join(SRC, name), "utf8");
  const original = parseAbc(source);
  const roundtrip = parseAbc(emitAbc(parse123(emit123(original))));
  const a = noteEvents(original);
  const b = noteEvents(roundtrip);

  let nonChord = 0;
  let exact = 0;
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i].sourceChordNotes > 1) continue; // 简谱不显示和弦堆
    nonChord++;
    if (sameNote(a[i], b[i])) exact++;
  }

  totalNonChord += nonChord;
  totalExact += exact;
  if (nonChord > 0) {
    filesWithNonChordNotes.push(stem);
    if (exact === nonChord && a.length === b.length) filesExact++;
  } else {
    filesWithoutNonChordNotes.push(stem);
  }
  perFile[stem] = { non_chord_notes: nonChord, exact };
}

const result = {
  dataset: "abc2kern/data/abc (30 files)",
  metric: "onset, duration, MIDI pitch",
  exclude_chord_stacks: true,
  notes: "Chord-stack events are excluded because 123/jianpu only keeps the top note.",
  files_total: files.length,
  files_with_non_chord_notes: filesWithNonChordNotes.length,
  files_exact: filesExact,
  files_without_non_chord_notes: filesWithoutNonChordNotes,
  total_non_chord_notes: totalNonChord,
  exact: totalExact,
  accuracy: totalNonChord ? totalExact / totalNonChord : 1,
  per_file: perFile,
};

const outDir = path.join(ROOT, "results");
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "accuracy.json"), JSON.stringify(result, null, 2) + "\n");

console.log(
  `non-chord notes: ${totalExact}/${totalNonChord} = ` +
    `${(100 * result.accuracy).toFixed(2)}%; ` +
    `files exact: ${filesExact}/${filesWithNonChordNotes.length}`,
);
console.log(`wrote ${path.join(outDir, "accuracy.json")}`);
