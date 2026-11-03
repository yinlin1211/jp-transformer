"""SVG → single-page PDF, using Chrome so embedded Bravura/CJK render correctly."""
import os, re, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
svg_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "棠梨煎雪_混排.svg")
pdf_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "棠梨煎雪_混排.pdf")

svg = open(svg_path, encoding="utf8").read()
m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
w, h = float(m.group(1)), float(m.group(2))
html = f"""<!doctype html><meta charset="utf-8">
<style>
@page {{ size: {w}pt {h}pt; margin: 0; }}
html, body {{ margin: 0; padding: 0; background: white; }}
svg {{ width: {w}pt; height: {h}pt; display: block; }}
</style>
{svg}"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    page = browser.new_page()
    page.set_content(html, wait_until="load")
    page.wait_for_timeout(1200)
    page.pdf(path=pdf_path, prefer_css_page_size=True, print_background=True)
    browser.close()
print("wrote", pdf_path, f"{w}x{h}pt")
