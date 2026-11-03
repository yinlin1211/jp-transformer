"""Render one case's MusicXML through Dolce's Mixed (staff + jianpu) view.

Usage: python3 scripts/render_mixed.py cases/<case>
Writes cases/<case>/mixed.svg (self-contained, long page).
"""
import base64, os, re, sys, time
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = "http://127.0.0.1:5180/"
FONT = os.environ.get("BRAVURA_FONT", os.path.join(HERE, "Bravura.woff2"))
FONT_B64 = base64.b64encode(open(FONT, "rb").read()).decode()


def finalize(svg: str) -> str:
    svg = svg.replace(
        "<svg ",
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ',
        1,
    )
    style = (
        '<style>@font-face{font-family:"Bravura";src:url(data:font/woff2;base64,'
        + FONT_B64
        + ') format("woff2");}</style>'
    )
    svg = re.sub(r"(<svg[^>]*>)", lambda m: m.group(1) + style, svg, count=1)
    # 编辑器的小节拍数告警层只属于界面；抽成独立 SVG 后没有配套 CSS，
    # `<rect class="vis-beat">` 会变成黑色实心块。导出前整层移除。
    svg = re.sub(r'<g class="vis-overlay".*?</g>', "", svg, flags=re.S)
    return svg


def import_xml(page, xml_path):
    page.wait_for_selector("text=Open score", timeout=30000)
    with page.expect_file_chooser(timeout=20000) as fc:
        page.get_by_text("Open score", exact=False).first.click()
    fc.value.set_files(xml_path)
    page.wait_for_timeout(1200)
    keep = page.get_by_text("Keep MusicXML (view as staff)", exact=False)
    if keep.count():
        keep.first.click()
        cb = page.locator("input[type=checkbox]")
        if cb.count():
            try:
                cb.first.check()
            except Exception:
                pass
        page.get_by_role("button", name="OK").click()
        page.wait_for_timeout(800)
    page.get_by_role("button", name="Mixed").click(timeout=15000)
    page.wait_for_selector(".score-page.mixed-page", timeout=30000)
    page.wait_for_timeout(800)
    # 混排档默认 155×240mm 会分页；切「长图」把整曲排成一张。
    page.evaluate(
        """() => {
            const app = window.__app;
            if (!app || !app.applyRenderSettings) throw new Error("window.__app missing");
            app.applyRenderSettings({ staffPaper: "长图" });
        }"""
    )
    page.wait_for_timeout(2500)
    page.wait_for_selector(".score-page.mixed-page", timeout=30000)
    svg = page.evaluate(
        """() => {
            const pages = [...document.querySelectorAll(".score-page.mixed-page")];
            pages.sort((a, b) => b.getBoundingClientRect().height - a.getBoundingClientRect().height);
            return pages[0] ? pages[0].outerHTML : "";
        }"""
    )
    return svg


def render_case(page, case_dir, out=None):
    case_dir = os.path.abspath(case_dir)
    xml = os.path.join(case_dir, "score.musicxml")
    out = out or os.path.join(case_dir, "mixed.svg")
    if not os.path.exists(xml):
        raise FileNotFoundError(xml)
    svg = finalize(import_xml(page, xml))
    open(out, "w", encoding="utf8").write(svg)
    return out, len(svg)


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "cases", "棠梨煎雪")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"]
        )
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()
        page.on("dialog", lambda dlg: dlg.accept())
        page.set_default_timeout(20000)
        page.goto(APP, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(500)
        t0 = time.time()
        out, n = render_case(page, case)
        print(f"wrote {out} bytes={n} in {time.time()-t0:.1f}s")
        ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
