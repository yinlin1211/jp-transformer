"""Build 123 from the official written measures (line_*.json), then MusicXML.

Why: raw c123 DSL has dialect quirks (cross-bar ties, endings inside slurs,
beam markers split by tags). The official runtime already normalizes each written
measure in `download/669切分单行/<song>/line_*.json`; using that as the source
keeps the measure grid and total duration identical to playback_full.
"""
from __future__ import annotations

import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WS = os.environ.get("JIANPU_WORKSPACE", "/path/to/workspace")
PB = os.environ.get("JIANPU_PLAYBACK", os.path.join(WS, "playback"))
ANN = os.environ.get("JIANPU_ANN", os.path.join(WS, "annotation58"))
RAW = os.environ.get("JIANPU_RAW", os.path.join(WS, "raw_jianpu"))

sys.path.insert(0, HERE)
import jp123_bidir as C


def songs():
    out = []
    for p in sorted(glob.glob(ANN + "/*/")):
        name = os.path.basename(p.rstrip("/"))
        if name.startswith("_"):
            continue
        out.append(name)
    return out


def load_lines(sid):
    fs = glob.glob(f"{PB}/{sid}_*/line_*.json")
    by = {}
    for f in fs:
        d = json.load(open(f, encoding="utf8"))
        by[d.get("measure_index")] = d
    return by


def written_indices(sid):
    p = glob.glob(f"{PB}/{sid}_*/playback_full.json")
    if not p:
        return None
    d = json.load(open(p[0], encoding="utf8"))
    ev = [e for e in d["events"] if e.get("source_occurrence") == 1]
    return sorted(set(e["measure_index"] for e in ev)), d


def measure_to_123(notation, losses):
    atoms = C._scan_ours(notation or "")
    toks = []
    for a in atoms:
        if a.kind == "bar":
            continue
        toks.extend(C._atom_to_123(a, losses))
    return " ".join(t for t in toks if t)


def build_lyrics(lines, idx, max_verse=1):
    verses = [[] for _ in range(max_verse)]
    for m in idx:
        o = lines[m]
        ly = o.get("lyric") or []
        slots = o.get("slots") or 0
        for v in range(max_verse):
            s = ly[v] if v < len(ly) else ""
            chars = s.replace(" ", "")
            if slots and len(chars) < slots:
                chars += "_" * (slots - len(chars))
            verses[v].append(chars)
    return [" ".join(x for x in v if x) for v in verses]


def main():
    cases = os.path.join(ROOT, "cases")
    os.makedirs(cases, exist_ok=True)
    report = {}
    for name in songs():
        sid = name.split("_")[0]
        wi = written_indices(sid)
        if not wi:
            report[name] = {"error": "no-playback"}
            continue
        idx, pb = wi
        lines = load_lines(sid)
        if any(m not in lines for m in idx):
            report[name] = {"error": "missing-line"}
            continue
        # skip {play} songs by checking raw source
        raws = glob.glob(os.path.join(RAW, f"{sid}_*", "*.json"))
        if raws:
            raw = json.load(open(raws[0], encoding="utf8"))["songdata"].get("notation", "")
            if re.search(r"\{play\s*:", raw):
                report[name] = {"skipped": "has-play"}
                continue
        first = lines[idx[0]]
        key = first.get("keynote") or pb.get("key_signature") or "1=C"
        rhythm = first.get("rhythm") or pb.get("rhythm") or "4/4"
        bpm = first.get("bpm") or pb.get("bpm") or 90
        losses = []
        measures = [measure_to_123(lines[m].get("notation"), losses) for m in idx]
        body = " | ".join(measures) + " |]"
        verses = build_lyrics(lines, idx)
        text = "\n".join([
            "X:1", f"T:{name.split('_', 1)[-1]}", f"K:{key}", f"M:{rhythm}",
            f"Q:1/4={int(bpm)}", f"%JIANPU-KEYNOTE:{key}",
            "%JIANPU-SOURCE:official-line-measures",
            body,
        ] + [f"w:{v}" for v in verses if v] + [""])
        d = os.path.join(cases, name)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "score.123"), "w", encoding="utf8").write(text)
        report[name] = {"source": "official-line", "measures": len(measures),
                        "losses": losses[:20], "verses": len([v for v in verses if v])}
        print(name, "ok", len(measures), "losses", losses[:6], flush=True)
    json.dump(report, open(os.path.join(ROOT, "report_lines.json"), "w", encoding="utf8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
