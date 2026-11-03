"""Compare our MusicXML measure durations against the official playback_full.

Official written measures = events with source_occurrence == 1, grouped by
measure_index. Our measures = sum of note/forward/backup durations in score.musicxml.
"""
import glob, json, os, xml.etree.ElementTree as ET

ROOT = os.environ.get("JIANPU_WORKSPACE", "/path/to/workspace")
HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.normpath(os.path.join(HERE, "..", "cases"))
PB = os.environ.get("JIANPU_PLAYBACK", os.path.join(ROOT, "playback"))


def official_written(sid):
    p = glob.glob(f"{PB}/{sid}_*/playback_full.json")
    if not p:
        return None
    ev = json.load(open(p[0], encoding="utf8"))["events"]
    if any("source_occurrence" in e for e in ev):
        ev = [e for e in ev if e.get("source_occurrence") == 1]
    by = {}
    for e in ev:
        m = e.get("measure_index")
        dur = e.get("duration_beat")
        if dur is None:
            dur = e.get("note_duration_beat")
        by[m] = by.get(m, 0.0) + (dur or 0.0)
    return [round(by[k], 6) for k in sorted(by)]


def ours(path):
    root = ET.parse(path).getroot()
    out, div = [], 1
    for m in root.findall(".//part/measure"):
        for a in m.findall("attributes"):
            d = a.findtext("divisions")
            if d:
                div = int(d)
        pos = 0
        for el in m:
            if el.tag == "note":
                if el.find("chord") is None:
                    pos += int(el.findtext("duration") or 0)
            elif el.tag == "forward":
                pos += int(el.findtext("duration") or 0)
            elif el.tag == "backup":
                pos -= int(el.findtext("duration") or 0)
        out.append(round(pos / div, 6))
    return out


def main():
    report = {}
    for name in sorted(os.listdir(CASES)):
        d = os.path.join(CASES, name)
        if not os.path.isdir(d):
            continue
        sid = name.split("_")[0]
        off = official_written(sid)
        xml = os.path.join(d, "score.musicxml")
        if off is None or not os.path.exists(xml):
            report[name] = {"error": "missing"}
            continue
        me = ours(xml)
        n = min(len(off), len(me))
        diffs = [round(me[i] - off[i], 6) for i in range(n)]
        bad = [(i + 1, off[i], me[i], diffs[i]) for i in range(n) if abs(diffs[i]) > 1e-6]
        total_off, total_me = round(sum(off), 6), round(sum(me), 6)
        delta = round(total_me - total_off, 6)
        if abs(delta) <= 1e-6 and not bad:
            status = "ok"
        elif abs(delta) <= 1e-6:
            status = "barline-shift"
        else:
            status = "time-error"
        report[name] = {
            "status": status,
            "official_measures": len(off), "ours_measures": len(me),
            "official_total": total_off, "ours_total": total_me, "total_delta": delta,
            "mismatch_measures": len(bad),
            "max_abs_delta": round(max((abs(x[3]) for x in bad), default=0.0), 6),
            "examples": bad[:12],
        }
        print(f"{name:24s} {status:14s} total {total_off:7.2f}->{total_me:7.2f} "
              f"delta {delta:+.2f} bad {len(bad):2d} max {report[name]['max_abs_delta']:.2f}", flush=True)
    json.dump(report, open(os.path.join(HERE, "..", "report_durations.json"), "w", encoding="utf8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    print(Counter(v.get("status") for v in report.values()))


if __name__ == "__main__":
    main()
