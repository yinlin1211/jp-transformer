"""Build the batch index page from per-case outputs and audit reports."""
import html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES = os.path.join(ROOT, "cases")


def load(name):
    p = os.path.join(ROOT, name)
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}


def main():
    conv = load("report_convert.json")
    dur = load("report_durations.json")
    rend = load("render_status.json")
    cards, counts = [], {"ok": 0, "barline-shift": 0, "time-error": 0, "render-fail": 0}
    for name in sorted(os.listdir(CASES)):
        d = os.path.join(CASES, name)
        if not os.path.isdir(d):
            continue
        c = conv.get(name, {})
        u = dur.get(name, {})
        r = rend.get(name, {})
        status = u.get("status", "unknown")
        if not r.get("ok"):
            status = "render-fail"
        counts[status] = counts.get(status, 0) + 1
        pill = {
            "ok": ("逐小节一致", "ok"),
            "barline-shift": ("总时值一致 · 小节线偏移", "warn"),
            "time-error": (f"总时值差 {u.get('total_delta', '?')} 拍", "bad"),
            "render-fail": ("混排渲染失败", "bad"),
        }.get(status, (status, "warn"))
        losses = c.get("losses", [])
        loss_txt = " · ".join(losses[:6]) + (" …" if len(losses) > 6 else "")
        has_svg = os.path.exists(os.path.join(d, "mixed.svg"))
        thumbs = []
        for label, fn in [("原谱简谱", "original_jianpu.png"), ("y123 混排", "mixed.png")]:
            if os.path.exists(os.path.join(d, fn)):
                thumbs.append(
                    f'<figure><img loading="lazy" src="cases/{html.escape(name)}/{fn}" '
                    f'alt="{html.escape(name)} {label}"><figcaption>{label}</figcaption></figure>'
                )
        thumb = ('<div class="thumbs">' + ''.join(thumbs) + '</div>'
                 if thumbs else '<div class="missing">未生成</div>')
        links = []
        for label, fn in [("原谱 PNG", "original_jianpu.png"),
                          ("混排 PNG", "mixed.png"), ("123", "score.123"),
                          ("MusicXML", "score.musicxml")]:
            if os.path.exists(os.path.join(d, fn)):
                links.append(f'<a href="cases/{html.escape(name)}/{fn}">{label}</a>')
        cards.append(f'''
<section class="case">
  <div class="head"><h3>{html.escape(name)}</h3><span class="pill {pill[1]}">{pill[0]}</span></div>
  <p class="meta">官方 {u.get('official_measures','?')} 小节 / {u.get('official_total','?')} 拍 ·
     我方 {u.get('ours_measures','?')} 小节 / {u.get('ours_total','?')} 拍 ·
     差 {u.get('total_delta','?')} 拍 · 失配小节 {u.get('mismatch_measures','?')}</p>
  <div class="thumb">{thumb}</div>
  <p class="loss">losses: {html.escape(loss_txt) or '—'}</p>
  <div class="links">{''.join(links)}</div>
</section>''')
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>非 play 歌曲 · c123 → y123 → MusicXML → 混排</title>
<style>
:root{{--ink:#1a202c;--muted:#718096;--line:#e2e8f0;--bg:#f7fafc;--accent:#2b6cb0}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:32px 20px 80px}} h1{{font-size:26px;margin:0 0 6px}}
.lede{{color:var(--muted);margin:0 0 18px}} .summary{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}}
.summary span{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:3px 11px;font-size:13px}}
.case{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 20px}}
.head{{display:flex;justify-content:space-between;gap:12px;align-items:center}} .head h3{{margin:0;font-size:17px}}
.pill{{font-size:12px;border-radius:999px;padding:2px 10px;white-space:nowrap}}
.pill.ok{{background:#e6fffa;color:#1c6b5f}} .pill.warn{{background:#fffaf0;color:#975a16}} .pill.bad{{background:#fff5f5;color:#9b2c2c}}
.meta{{color:var(--muted);font-size:13px;margin:6px 0 10px}}
.thumbs{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.thumbs figure{{margin:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff}}
.thumbs img{{width:100%;display:block;max-height:520px;object-fit:cover;object-position:top}}
.thumbs figcaption{{font-size:12px;color:var(--muted);padding:4px 8px;border-top:1px solid var(--line)}}
.missing{{padding:40px;text-align:center;color:var(--muted)}}
.loss{{font-size:12px;color:var(--muted);word-break:break-all}} .links{{display:flex;gap:8px;flex-wrap:wrap}}
.links a{{font-size:12px;border:1px solid var(--line);border-radius:6px;padding:3px 9px;color:var(--accent);text-decoration:none;background:#f8fafc}}
</style></head><body><main>
<h1>非 <code>{{play}}</code> 歌曲 · c123 → y123 → MusicXML → 混排</h1>
<p class="lede">58 首里排除 36 首含 <code>{{play}}</code> 的，剩 22 首；21 首已出混排，遇萤 进 Dolce Mixed 失败。
时值核对口径：官方 <code>playback_full</code>（source_occurrence=1）逐小节 duration 求和 vs 我方 MusicXML 小节时值。
· <a href="https://github.com/yinlin1211/jp-transformer/blob/main/123toxml/NOTATION.md">记谱方法</a>
· <a href="https://github.com/yinlin1211/jp-transformer/blob/main/123toxml/README.md">README</a></p>
<div class="summary"><span>共 22 首</span><span>逐小节一致 {counts.get('ok',0)}</span>
<span>总时值一致/小节线偏移 {counts.get('barline-shift',0)}</span>
<span>总时值有差 {counts.get('time-error',0)}</span>
<span>混排失败 {counts.get('render-fail',0)}</span></div>
{''.join(cards)}
</main></body></html>'''
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf8").write(page)
    print("wrote index.html", counts)


if __name__ == "__main__":
    main()
