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


# ── Yanesideki bayat gomulu sidecar (2026-10-16 duzeltmesi) ──────────────
# Olcuilen neden: install.sh kabukla birlikte 17 Eyl'luk PyInstaller sidecar'ini
# de /usr/lib/pkgforge/desktop/'a kopyalamisti; kabuk onu sectigi icin GUI bir
# aydir BAYAT motor calistirirken CLI taze kodu calistiriyordu.

def _env_ile_calistir(monkeypatch, binary):
    """_launch_desktop'un kurduyu ortamı yakala (gerçek subprocess yok)."""
    import subprocess

    captured: dict[str, object] = {}

    def fake_call(cmd, env=None):
        captured["cmd"] = cmd
        captured["env"] = dict(env or {})
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)
    assert main._launch_desktop(binary, []) == 0
    return captured["env"]


def test_agac_icindeki_kabuk_canli_python_sidecar_kullanir(monkeypatch):
    root = Path(main.__file__).resolve().parent
    kabuk = root / "desktop/src-tauri/target/release/pkgforge-desktop"
    monkeypatch.delenv("PKGFORGE_SIDECAR", raising=False)
    env = _env_ile_calistir(monkeypatch, kabuk)
    assert env["PKGFORGE_SIDECAR"] == "python"


def test_usr_lib_kurulumu_da_canli_python_kullanir(monkeypatch, tmp_path):
    """Sahte /usr/lib/pkgforge kurulumu: kabuk agacin icinde -> python."""
    kok = tmp_path / "usr/lib/pkgforge"
    (kok / "desktop").mkdir(parents=True)
    kabuk = kok / "desktop/pkgforge-desktop"
    kabuk.write_text("#!/bin/sh\n", encoding="utf-8")
    (kok / "main.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(main, "__file__", str(kok / "main.py"))
    monkeypatch.delenv("PKGFORGE_SIDECAR", raising=False)
    env = _env_ile_calistir(monkeypatch, kabuk)
    assert env["PKGFORGE_SIDECAR"] == "python"


def test_agac_disindaki_kabuk_gomulu_sidecar_tercih_edilir(monkeypatch, tmp_path):
    """Kabuk bizim agacimizda degilse (gercek paket kurulumu) varsayilan kalir."""
    disari = tmp_path / "opt/pkgforge-desktop"
    disari.parent.mkdir(parents=True, exist_ok=True)
    disari.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.delenv("PKGFORGE_SIDECAR", raising=False)
    env = _env_ile_calistir(monkeypatch, disari)
    assert "PKGFORGE_SIDECAR" not in env


def test_venv_yoksa_sidecar_ayni_interpreteri_kullaniyor(monkeypatch, tmp_path):
    """PKGFORGE_PYTHON: .venv yoksa CLI'yi calistiran interpreter'in kendisi."""
    import sys

    tree = tmp_path / "tree"
    tree.mkdir()
    disari = tmp_path / "opt/pkgforge-desktop"
    disari.parent.mkdir(parents=True, exist_ok=True)
    disari.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(main, "__file__", str(tree / "main.py"))
    monkeypatch.delenv("PKGFORGE_PYTHON", raising=False)
    env = _env_ile_calistir(monkeypatch, disari)
    assert env["PKGFORGE_PYTHON"] == sys.executable


def test_ayni_ekli_kardes_dizin_agac_icin_sayilmaz(tmp_path):
    """Prefix tuzagi: 'pkgforge-extra' -> 'pkgforge' agacinin icinde degildir."""
    kok = tmp_path / "pkgforge"
    kok.mkdir()
    kardes = tmp_path / "pkgforge-extra/desktop"
    kardes.mkdir(parents=True)
    dis = kardes / "pkgforge-desktop"
    dis.write_text("x", encoding="utf-8")
    assert main._kurulum_agaci_icinde(dis, kok) is False

    ic = kok / "desktop"
    ic.mkdir(parents=True)
    ic_ab = ic / "pkgforge-desktop"
    ic_ab.write_text("x", encoding="utf-8")
    assert main._kurulum_agaci_icinde(ic_ab, kok) is True
