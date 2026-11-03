import fs from "node:fs";
import path from "node:path";
// Point DOLCE_J123 at the Dolce build's j123.js (or place j123.js next to
// this script). The module is not vendored here because it belongs to Dolce.
const J123 = process.env.DOLCE_J123 || path.resolve("j123.js");
const {
  parse123, scoreDocToMusicXml, playSourceOf, buildTimeline,
} = await import(J123);

const ROOT = path.resolve(process.argv[2] || ".");
const CASES = path.join(ROOT, "cases");
const r = (n) => Math.round(n * 1e9) / 1e9;
const report = {};

for (const id of fs.readdirSync(CASES).sort()) {
  const dir = path.join(CASES, id);
  if (!fs.statSync(dir).isDirectory()) continue;
  const p123 = path.join(dir, "score.123");
  if (!fs.existsSync(p123)) continue;
  try {
    const text = fs.readFileSync(p123, "utf8");
    const doc = parse123(text);
    const xml = scoreDocToMusicXml(doc);
    fs.writeFileSync(path.join(dir, "score.musicxml"), xml);
    const src = playSourceOf(doc);
    const tl = buildTimeline(src);
    const notes = tl.notes.map((n) => ({
      onset: r(n.t0), duration: r(n.t1 - n.t0), midi: n.pitch,
      lyric: n.lyric && n.lyric !== "-" ? n.lyric : null,
    }));
    fs.writeFileSync(path.join(dir, "timeline_123.json"),
      JSON.stringify({ notes, duration: r(tl.duration) }, null, 1));
    const ms = doc.songs[0].parts[0].measures;
    let writtenNotes = 0, lyricChords = 0;
    for (const m of ms) for (const el of m.elements) {
      if (el.kind !== "chord" || el.rest) continue;
      writtenNotes += el.notes.length;
      if (el.lyrics?.length) lyricChords++;
    }
    let repF = 0, repB = 0, endings = 0;
    for (const m of ms) for (const b of m.barlines || []) {
      if (b.repeat === "forward") repF++;
      if (b.repeat === "backward") repB++;
      if (b.ending) endings++;
    }
    const diag = (doc.diagnostics || []).map((d) =>
      typeof d === "string" ? d : `${d.severity || ""}:${d.code || ""}:${d.message || ""}`);
    report[id] = {
      measures: ms.length, writtenNotes, lyricChords,
      timelineNotes: notes.length, playItems: src?.playData?.measures?.length ?? 0,
      repeatForward: repF, repeatBackward: repB, endings,
      xmlRepeat: (xml.match(/<repeat/g) || []).length,
      xmlEnding: (xml.match(/<ending/g) || []).length,
      xmlNotes: (xml.match(/<note/g) || []).length,
      xmlLen: xml.length,
      diag,
    };
    console.log(id, JSON.stringify(report[id]));
  } catch (e) {
    report[id] = { error: String((e && e.message) || e) };
    console.log(id, "ERR", report[id].error);
  }
}
fs.writeFileSync(path.join(ROOT, "report_xml.json"), JSON.stringify(report, null, 1));
