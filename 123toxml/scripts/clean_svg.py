"""Strip Dolce's editor-only beat overlay from exported SVGs and save its warnings.

Usage: python3 scripts/clean_svg.py [case ...]
"""
import glob, html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES = os.path.join(ROOT, "cases")
OVERLAY = re.compile(r'<g class="vis-overlay"[^>]*data-beats="([^"]*)"[^>]*>.*?</g>', re.S)
DEFAULT = re.compile(r'<g class="vis-overlay".*?</g>', re.S)


def clean(case_dir):
    p = os.path.join(case_dir, "mixed.svg")
    if not os.path.exists(p):
        return None
    s = open(p, encoding="utf8").read()
    warnings = []
    m = OVERLAY.search(s)
    if m:
        try:
            data = json.loads(html.unescape(m.group(1)))
            for w in data:
                titles = [x for x in w if isinstance(x, str) and ("Measure" in x or "beat" in x)]
                if titles:
                    warnings.append(titles[0])
        except Exception:
            pass
    s = OVERLAY.sub("", s)
    s = DEFAULT.sub("", s)
    open(p, "w", encoding="utf8").write(s)
    if warnings:
        json.dump(warnings, open(os.path.join(case_dir, "beat_warnings.json"), "w", encoding="utf8"),
                  ensure_ascii=False, indent=1)
    return warnings


def main():
    names = sys.argv[1:] or [os.path.basename(d) for d in glob.glob(os.path.join(CASES, "*")) if os.path.isdir(d)]
    total = 0
    for name in names:
        w = clean(os.path.join(CASES, name))
        if w:
            total += len(w)
            print(name, "warnings", len(w), w[:3])
        else:
            print(name, "clean" if w == [] else "no-svg")
    print("total warnings", total)


if __name__ == "__main__":
    main()
