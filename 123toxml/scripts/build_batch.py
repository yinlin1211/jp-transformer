"""把 annotation58 的 58 首 c123 统一转成 123，并生成 MusicXML。

写谱形态：保留 |: :|、房号、跳转；{play}/{section}/{ms} 不进谱面（记为 loss）。
"""
from __future__ import annotations

import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WS = os.environ.get("JIANPU_WORKSPACE", "/path/to/workspace")
RAW = os.environ.get("JIANPU_RAW", os.path.join(WS, "raw_jianpu"))
PB = os.environ.get("JIANPU_PLAYBACK", os.path.join(WS, "playback"))
ANN = os.environ.get("JIANPU_ANN", os.path.join(WS, "annotation58"))

sys.path.insert(0, HERE)
import jp123_bidir as C


def songs():
    out = []
    for p in sorted(glob.glob(ANN + "/*/")):
        name = os.path.basename(p.rstrip("/"))
        if name.startswith("_"):
            continue
        sid = name.split("_")[0]
        cands = [q for q in glob.glob(RAW + "/*/*.json")
                 if os.path.basename(os.path.dirname(q)).split("_")[0] == sid]
        out.append((name, sid, cands[0] if cands else None))
    return out


def playback_bpm(sid: str):
    p = glob.glob(f"{PB}/{sid}_*/playback_full.json")
    if not p:
        return None
    try:
        return json.load(open(p[0], encoding="utf8")).get("bpm")
    except Exception:
        return None


def main():
    cases = os.path.join(ROOT, "cases")
    os.makedirs(cases, exist_ok=True)
    report = {}
    for name, sid, src in songs():
        rec = {"song": name, "sid": sid, "source": src}
        if not src:
            rec["error"] = "source-missing"
            report[name] = rec
            continue
        try:
            sd = json.load(open(src, encoding="utf8"))["songdata"]
        except Exception as e:
            rec["error"] = f"read:{e}"
            report[name] = rec
            continue
        sd["song_name"] = name.split("_", 1)[-1]
        # 本轮只做非 {play} 的歌；{play} 的全曲演奏顺序不在写谱里展开。
        if re.search(r"\{play\s*:", str(sd.get("notation", ""))):
            rec["skipped"] = "has-play"
            report[name] = rec
            print(name, "skip has-play", flush=True)
            continue
        if not sd.get("bpm"):
            bpm = playback_bpm(sid)
            if bpm:
                sd["bpm"] = bpm
                rec["bpm_from_playback"] = bpm
        try:
            r = C.ours_to_123(sd)
        except Exception as e:
            rec["error"] = f"convert:{e}"
            report[name] = rec
            continue
        rec["losses"] = r["losses"]
        rec["header"] = r["header"]
        if not r["text"]:
            rec["error"] = "empty-123"
            report[name] = rec
            continue
        d = os.path.join(cases, name)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "score.123"), "w", encoding="utf8").write(r["text"])
        n = r["text"]
        body = "\n".join(l for l in n.splitlines() if l and not l.startswith(("X:", "T:", "K:", "M:", "Q:", "V:", "%", "w:")))
        rec["repeat_forward"] = body.count("|:")
        rec["repeat_backward"] = body.count(":|")
        rec["ending_open"] = len(re.findall(r"\[\d", body))
        rec["final_bar"] = body.count("|]")
        rec["has_play"] = "play-linearized" in r["losses"]
        rec["has_house"] = "section-labels-stripped" in r["losses"] or rec["ending_open"] > 0
        report[name] = rec
        print(name, "ok", len(n), "losses", r["losses"], flush=True)
    json.dump(report, open(os.path.join(ROOT, "report_convert.json"), "w", encoding="utf8"),
              ensure_ascii=False, indent=1)
    print("done", len(report), flush=True)


if __name__ == "__main__":
    main()
