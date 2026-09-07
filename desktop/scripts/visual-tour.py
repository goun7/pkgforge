"""S2: headless visual tour — serves desktop/dist, walks all sidebar pages.

- Asserts every page renders non-blank (no white-screen regressions).
- Saves screenshots to docs/screens/ for README + release review.
- Backend (Tauri invoke) is absent in plain Chromium: pages show their
  empty/disconnected states, which is exactly what layout QA needs.
  (Full interactive QA happens in the Tauri runtime on a real device.)

Usage:
    python3 desktop/scripts/visual-tour.py [--serve-dir desktop/dist]
    CHROMIUM_EXE=/path/to/chrome python3 desktop/scripts/visual-tour.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

URL = "http://127.0.0.1:18778/"
PAGES = [
    ("Dönüştür", "Dönüştür"),
    ("Kurulanlar", "Kurulanlar"),
    ("Raporlar", "Raporlar"),
    ("AUR Gözat", "AUR"),
    ("Güncellemeler", "Güncellemeler"),
    ("Güvenlik", "Güvenlik"),
    ("Karşılaştır", "Karşılaştır"),
    ("Dışa Aktar", "Dışa Aktar"),
    ("Araçlar", "Araçlar"),
    ("Eklentiler", "Eklentiler"),
    ("Fleet", "Fleet"),
    ("Ayarlar", "Ayarlar"),
]
SHOTS = {"Dönüştür": "convert", "Kurulanlar": "installed",
         "Güvenlik": "security", "Ayarlar": "settings"}
TOAST_CLOSE = (
    "button[aria-label='Bildirimi kapat'],"
    "button[aria-label='Dismiss notification']"
)


def dismiss_toasts(page) -> None:
    """Close stacked error toasts (browser-only: no Tauri backend here)."""
    try:
        for btn in page.locator(TOAST_CLOSE).all():
            try:
                btn.click(timeout=500)
            except Exception:  # noqa: BLE001, S110 - best-effort toast cleanup
                pass
    except Exception:  # noqa: BLE001, S110 - tour must not crash on UI drift
        pass


def main() -> int:
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[2]
    serve_dir = Path(sys.argv[sys.argv.index("--serve-dir") + 1]) \
        if "--serve-dir" in sys.argv else root / "desktop" / "dist"
    out_dir = root / "docs" / "screens"
    out_dir.mkdir(parents=True, exist_ok=True)

    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", "18778"],
        cwd=str(serve_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    failures: list[str] = []
    try:
        with sync_playwright() as p:
            exe = os.environ.get("CHROMIUM_EXE")
            kwargs = {"args": ["--no-sandbox"]}
            if exe:
                kwargs["executable_path"] = exe
            browser = p.chromium.launch(**kwargs)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(URL, wait_until="networkidle")
            page.wait_for_timeout(1500)
            # Dismiss the welcome tour if present.
            for sel in ["button:has-text('Başla')", "button[aria-label='Kapat']"]:
                try:
                    page.click(sel, timeout=1500)
                    break
                except Exception:  # noqa: BLE001, S110 - tour overlay may be absent
                    pass
            page.wait_for_timeout(500)
            for name, want_title in PAGES:
                page.get_by_role("button", name=name, exact=True).first.click(
                    timeout=5000)
                page.wait_for_timeout(800)
                # Navigation proof: the page heading must appear.
                try:
                    page.get_by_role(
                        "heading", name=want_title, exact=False).first.wait_for(
                            timeout=3000)
                except Exception:  # noqa: BLE001 - recorded as failure below
                    failures.append(f"{name}: heading '{want_title}' missing")
                    continue
                body = page.inner_text("body")
                if len(body.strip()) < 50:
                    failures.append(f"{name}: blank page ({len(body)} chars)")
                else:
                    print(f"  ok {name} ({len(body)} chars)")
                if name in SHOTS:
                    # Toasts respawn while pages poll the (absent) backend;
                    # dismiss twice so captures stay readable. Any remaining
                    # toast is genuine page state, kept as-is.
                    dismiss_toasts(page)
                    page.wait_for_timeout(900)
                    dismiss_toasts(page)
                    page.screenshot(path=str(out_dir / f"{SHOTS[name]}.png"))
                    print(f"  shot {SHOTS[name]}.png")
            browser.close()
    finally:
        srv.terminate()
    if failures:
        print("VISUAL TOUR FAILED:")
        for f in failures:
            print(" -", f)
        return 1
    print(f"VISUAL TOUR OK ({len(PAGES)} pages, shots in docs/screens/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
