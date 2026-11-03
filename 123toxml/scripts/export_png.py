"""Rasterize a case's mixed.svg in Chrome at a fixed CSS width.

Usage: python3 scripts/export_png.py cases/<case> [width]
"""
import os, re, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))


def png_from_svg(page, svg_path, png_path, width=1400):
    svg = open(svg_path, encoding="utf8").read()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    if not m:
        raise ValueError("no viewBox: " + svg_path)
    w, h = float(m.group(1)), float(m.group(2))
    out_h = round(h * width / w)
    svg = svg.replace("<svg ", f'<svg width="{width}" height="{out_h}" ', 1)
    page.set_viewport_size({"width": width, "height": min(out_h, 30000)})
    page.set_content(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;padding:0;background:#fff}}svg{{display:block}}</style>{svg}', wait_until="load")
    page.wait_for_timeout(600)
    page.locator("svg").screenshot(path=png_path)
    return out_h


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "cases", "棠梨煎雪")
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1400
    case = os.path.abspath(case)
    svg = os.path.join(case, "mixed.svg")
    png = os.path.join(case, "mixed.png")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": width, "height": 1000}, device_scale_factor=2)
        h = png_from_svg(page, svg, png, width)
        print("wrote", png, f"{width}x{h}")
        browser.close()


if __name__ == "__main__":
    main()
