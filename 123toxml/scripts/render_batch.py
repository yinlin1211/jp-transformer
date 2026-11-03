"""Render all (or selected) cases through Dolce Mixed, one browser context reused."""
import json, os, sys, time
from playwright.sync_api import sync_playwright
from render_mixed import APP, import_xml, finalize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES = os.path.join(ROOT, "cases")


def all_cases():
    return sorted(d for d in os.listdir(CASES) if os.path.isdir(os.path.join(CASES, d)))


def render(page, name):
    d = os.path.join(CASES, name)
    xml = os.path.join(d, "score.musicxml")
    if not os.path.exists(xml):
        raise FileNotFoundError(xml)
    svg = finalize(import_xml(page, xml))
    open(os.path.join(d, "mixed.svg"), "w", encoding="utf8").write(svg)
    return {"svg_bytes": len(svg)}


def main():
    wanted = sys.argv[1:]
    names = wanted or all_cases()
    status_path = os.path.join(ROOT, "render_status.json")
    status = json.load(open(status_path, encoding="utf8")) if os.path.exists(status_path) else {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"]
        )
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000}, device_scale_factor=2)
        for name in names:
            if name in status and status[name].get("ok"):
                continue
            for attempt in (1, 2):
                page = None
                t0 = time.time()
                try:
                    page = ctx.new_page()
                    page.on("dialog", lambda dlg: dlg.accept())
                    page.set_default_timeout(20000)
                    page.goto(APP, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(500)
                    info = render(page, name)
                    status[name] = {"ok": True, **info, "seconds": round(time.time() - t0, 1)}
                    print(name, "ok", info, f"{time.time()-t0:.1f}s", flush=True)
                    break
                except Exception as e:
                    status[name] = {"ok": False, "attempt": attempt, "error": repr(e)[:300]}
                    print(name, "FAIL", attempt, repr(e)[:200], flush=True)
                finally:
                    if page is not None:
                        try:
                            page.close()
                        except Exception:
                            pass
            json.dump(status, open(status_path, "w", encoding="utf8"), ensure_ascii=False, indent=1)
        ctx.close()
        browser.close()
    print("done", sum(1 for v in status.values() if v.get("ok")), "/", len(status), flush=True)


if __name__ == "__main__":
    main()
