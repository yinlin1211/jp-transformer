"""棠梨煎雪：苍强统一简谱 → 悦谱 123（保留反复）。"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jp123_bidir_tangli as C

RAW = sys.argv[1] if len(sys.argv) > 1 else "/path/to/raw_jianpu/<song>/source_原始简谱.json"
# 源 JSON 无 bpm；取官方 playback_full 的 ♩=72 作为谱面速度。
BPM = 72

with open(RAW, encoding="utf8") as f:
    song = json.load(f)["songdata"]
song["bpm"] = BPM
r = C.ours_to_123(song)
assert r["text"], r["losses"]
out = os.path.join(HERE, "棠梨煎雪.123")
with open(out, "w", encoding="utf8") as f:
    f.write(r["text"])
print(json.dumps({"out": out, "losses": r["losses"], "header": r["header"]}, ensure_ascii=False, indent=1))
print("repeat:", r["text"].count("|:"), "back:", r["text"].count(":|"), "final:", r["text"].count("|]"))
