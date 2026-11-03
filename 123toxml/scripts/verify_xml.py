"""Verify MusicXML against the 123 timeline Dolce itself produced."""
import json, glob, os, sys
import xml.etree.ElementTree as ET
from fractions import Fraction
STEP = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}
FIFTHS = {"C":0,"G":1,"D":2,"A":3,"E":4,"B":5,"F#":6,"C#":7,
          "F":-1,"Bb":-2,"Eb":-3,"Ab":-4,"Db":-5,"Gb":-6,"Cb":-7}
def expected_fifths(keynote):
    if not keynote: return None
    k=keynote.split("=")[-1].strip().rstrip("m")
    import re; k=re.sub(r"\d+$","",k)
    if len(k)>=2 and k[0]=="b": k=k[1]+"b"
    elif len(k)>=2 and k[0]=="#": k=k[1]+"#"
    return FIFTHS.get(k[:1].upper()+k[1:])
def midi(step, alter, octv):
    return 12*(octv+1)+STEP[step]+int(alter or 0)
def parse(path):
    root=ET.parse(path).getroot()
    divisions=None; fifths=None; notes=[]; errors=[]
    open_chain=None
    cursor=0
    for measure in root.findall(".//part/measure"):
        pos=cursor
        for el in measure:
            if el.tag=="attributes":
                d=el.findtext("divisions")
                if d: divisions=int(d)
                f=el.find(".//key/fifths")
                if f is not None: fifths=int(f.text)
            elif el.tag=="backup":
                pos-=int(el.findtext("duration") or 0)
            elif el.tag=="forward":
                pos+=int(el.findtext("duration") or 0)
            elif el.tag=="note":
                dur=int(el.findtext("duration") or 0)
                if el.find("grace") is not None:
                    continue  # grace notes do not advance the timeline
                chord=el.find("chord") is not None
                if not chord: onset_units=pos; pos+=dur
                else: onset_units=notes[-1]["onset_units"] if notes else pos
                if divisions is None: errors.append("no divisions"); continue
                onset=Fraction(onset_units, divisions); duration=Fraction(dur, divisions)
                if el.find("rest") is not None:
                    continue
                pitch=el.find("pitch")
                if pitch is None: continue
                m=midi(pitch.findtext("step"), pitch.findtext("alter"), int(pitch.findtext("octave")))
                ties=[t.get("type") for t in el.findall("tie")]
                tieds=[t.get("type") for t in el.findall(".//notations/tied")]
                signs=set(ties+tieds)
                lyric=None
                ly=el.find("lyric/text")
                if ly is not None and ly.text and ly.text.strip() not in ("", "."):
                    lyric=ly.text.strip()
                if "stop" in signs and open_chain and open_chain["midi"]==m:
                    ch=open_chain; ch["duration"]+=duration
                    if "start" not in signs:
                        notes.append(ch); open_chain=None
                    continue
                entry={"onset_units":onset_units,"onset":onset,"duration":duration,"midi":m,"lyric":lyric}
                if "start" in signs:
                    open_chain=entry
                    if "stop" in signs:  # both: single-note chain
                        notes.append(entry); open_chain=None
                else:
                    notes.append(entry)
        cursor=pos
    return {"divisions":divisions,"fifths":fifths,"notes":notes,"errors":errors}
def main(root="cases"):
    rows=[]; total_bad=0
    for d in sorted(glob.glob(root+"/*/")):
        case=os.path.basename(d.rstrip("/"))
        meta=json.load(open(d+"meta.json",encoding="utf8"))
        tl=json.load(open(d+"timeline_123.json",encoding="utf8"))["notes"]
        xml=parse(d+"score.musicxml")
        diffs=[]
        if len(tl)!=len(xml["notes"]):
            diffs.append(f"count timeline={len(tl)} xml={len(xml['notes'])}")
        for i,(a,b) in enumerate(zip(tl,xml["notes"])):
            if abs(float(a["onset"])-float(b["onset"]))>1e-6 or abs(float(a["duration"])-float(b["duration"]))>1e-6 or int(a["midi"])!=int(b["midi"]) or (a.get("lyric") or None)!=(b.get("lyric") or None):
                diffs.append(f"#{i} tl={a} xml_onset={float(b['onset'])} xml_dur={float(b['duration'])} xml_midi={b['midi']} xml_lyric={b.get('lyric')}")
                if len(diffs)>8: break
        ef=expected_fifths(meta.get("keynote"))
        key_ok = ef is None or xml["fifths"]==ef
        ok=not diffs and key_ok and not xml["errors"]
        if not ok: total_bad+=1
        rec={"case":case,"ok":ok,"notes_source":len(tl),"notes_xml":len(xml["notes"]),
             "fifths":xml["fifths"],"fifths_expected":ef,"diffs":diffs,"errors":xml["errors"]}
        meta["verify"]=rec; meta["ok"]=ok
        json.dump(meta,open(d+"meta.json","w",encoding="utf8"),ensure_ascii=False,indent=1)
        rows.append(rec)
        if not ok: print(case, "FAIL", diffs[:3], "key", xml["fifths"], ef)
    print(f"verified {len(rows)} cases, pass {sum(r['ok'] for r in rows)}, fail {total_bad}")
    return total_bad
if __name__=="__main__":
    sys.exit(1 if main() else 0)
