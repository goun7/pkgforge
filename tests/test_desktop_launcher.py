"""Desktop launcher contract tests (main.py: `pkgforge desktop`).

Tauri ikilisi mevcutsa onu çalıştırır; yoksa nedenini söyleyip klasik
PyQt6 arayüzüne düşer. Hiçbir yol sessizce başarısız olmamalı.
"""

from __future__ import annotations

import sys
from pathlib import Path

import main


def test_env_override_resolves_desktop_binary(tmp_path, monkeypatch):
    fake = tmp_path / "pkgforge-desktop"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("PKGFORGE_DESKTOP_BIN", str(fake))
    assert main._find_desktop_binary() == fake


def test_missing_env_override_falls_through_to_candidates(monkeypatch):
    """Env boşsa ya mevcut bir ikili döner ya da None (deterministik kabul)."""
    monkeypatch.delenv("PKGFORGE_DESKTOP_BIN", raising=False)
    found = main._find_desktop_binary()
    assert found is None or found.is_file()


def test_desktop_launches_found_binary(monkeypatch, tmp_path):
    fake = tmp_path / "pkgforge-desktop"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    seen: dict[str, object] = {}

    monkeypatch.setattr(main, "_find_desktop_binary", lambda: fake)
    monkeypatch.setattr(
        main, "_launch_desktop",
        lambda binary, extra: seen.update(binary=binary, extra=extra) or 0,
    )
    monkeypatch.setattr(sys, "argv", ["pkgforge", "desktop", "pkg.deb"])
    monkeypatch.delenv("PKGFORGE_DESKTOP_BIN", raising=False)

    rc = main.main()
    assert rc == 0
    assert seen["binary"] == fake
    assert seen["extra"] == ["pkg.deb"]


def test_desktop_falls_back_with_notice_when_binary_missing(monkeypatch, capsys):
    monkeypatch.setattr(main, "_find_desktop_binary", lambda: None)
    # PyQt6 kurulu değil gibi davran: main() QApplication'a ulaşmadan döner.
    monkeypatch.setattr(main, "_check_pyqt6", lambda: False)
    monkeypatch.setattr(sys, "argv", ["pkgforge", "desktop"])

    rc = main.main()
    out = capsys.readouterr().out

    assert rc == 1
    # Kullanıcıya nedeni ve çözüm yolu gösterilmeli (sessiz çökme yok).
    assert main.tr("main.desktop_missing") in out
    assert main.tr("main.desktop_build_hint") in out
    assert main.tr("main.desktop_fallback") in out


def test_launch_failure_reports_error(monkeypatch):
    """İkili var ama çalışmıyorsa (OSError) kullanıcı bilgilendirilir."""
    import subprocess

    missing = Path("/nonexistent/pkgforge-desktop-ghost")
    monkeypatch.setattr(
        subprocess, "call",
        lambda cmd, env=None: (_ for _ in ()).throw(OSError(13, "permission")),
    )
    rc = main._launch_desktop(missing, [])
    assert rc == 1
