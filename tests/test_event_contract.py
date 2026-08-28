"""Faz 4 (F4.1) — sidecar/frontend push-event sözleşme testi.

Tauri v2 event adları yalnızca [A-Za-z0-9/_:-] kabul eder; nokta içeren bir ad
Rust tarafında IllegalEventName panic'i üretir (Faz 0-2 arası gizli kalan
kritik bug). Bu test sözleşmeyi kilide alır:
  1) sidecar'ın yaydığı HER push adı Tauri charset'ine uymalı,
  2) frontend'in dinlediği HER ad, sidecar tarafından gerçekten yayılmalı.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TAURI_EVENT_RE = re.compile(r"^[A-Za-z0-9/_:-]+$")
# Any "event/..." literal under core/ is an emit-site (incl. default args).
EVENT_LITERAL_RE = re.compile(r'"(event/[^"]+)"')


def _collect_emitted() -> set[str]:
    emitted: set[str] = set()
    for path in (PROJECT_ROOT / "core").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        emitted.update(EVENT_LITERAL_RE.findall(text))
    return emitted


def _collect_frontend_listened() -> set[str]:
    listened: set[str] = set()
    for base in ("desktop/src", "desktop/src-tauri/src"):
        root = PROJECT_ROOT / base
        assert root.is_dir(), f"missing {base}"
        for path in root.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".rs"} or not path.is_file():
                continue
            # Test dosyalari uretim frontend'i degildir; event adlarini mock/hata
            # mesajlarinda serbestce anabilirler (yanlis pozitif uretirler).
            if "__tests__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            listened.update(re.findall(r'"(event/[^"]+)"', text))
    return listened


def test_sidecar_emits_push_events():
    emitted = _collect_emitted()
    assert len(emitted) >= 10, "emitter regex broken or events removed"
    assert all(e.startswith("event/") for e in emitted)


def test_every_event_name_is_tauri_safe():
    bad = [e for e in _collect_emitted() if not TAURI_EVENT_RE.match(e)]
    assert not bad, (
        f"Tauri v2 rejects dotted/illegal event names (IllegalEventName panic): {bad}"
    )


def test_frontend_only_listens_to_emitted_events():
    emitted = _collect_emitted()
    unknown = _collect_frontend_listened() - emitted
    assert not unknown, f"frontend listens to events the sidecar never emits: {sorted(unknown)}"


def test_rust_relay_listener_is_emitted():
    # lib.rs app.listen("event/finished") panics at startup if invalid/unknown.
    assert "event/finished" in _collect_emitted()
