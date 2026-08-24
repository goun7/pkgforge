"""Faz 5 (F5.17) — restore_drill tatbikat gorevi."""
from __future__ import annotations

import sqlite3

import config
from core.cloud_sync import restore_drill


def _seed_config(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "settings.json").write_text('{"language": "tr"}', encoding="utf-8")
    conn = sqlite3.connect(root / "history.db")
    conn.execute("CREATE TABLE conversions (id INTEGER PRIMARY KEY,"
                 " package_name TEXT)")
    conn.execute("INSERT INTO conversions (package_name) VALUES ('x')")
    conn.commit()
    conn.close()


def test_restore_drill_roundtrip_ok(tmp_path, monkeypatch):
    fake_root = tmp_path / "cfg"
    _seed_config(fake_root)
    monkeypatch.setattr(config, "CONFIG_DIR", fake_root)

    result = restore_drill()
    assert result["ok"] is True
    assert "dogrulandi" in result["detail"]
    # Gercek kok degismemis olmali (tatbikat izole calisti).
    assert config.CONFIG_DIR == fake_root


def test_restore_drill_empty_config_still_ok(tmp_path, monkeypatch):
    fake_root = tmp_path / "empty"
    fake_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "CONFIG_DIR", fake_root)

    result = restore_drill()
    # Bos yapilandirmada da mekanik saglikli donmeli (0/0 dosya).
    assert result["ok"] is True


def test_restore_drill_registered_as_task():
    from core.scheduler import TASKS

    assert "restore_drill" in TASKS


def test_restore_drill_cleans_up_workdir(tmp_path, monkeypatch):
    import glob

    fake_root = tmp_path / "cfg"
    _seed_config(fake_root)
    monkeypatch.setattr(config, "CONFIG_DIR", fake_root)

    before = set(glob.glob("/tmp/pkgforge-drill-*"))
    restore_drill()
    after = set(glob.glob("/tmp/pkgforge-drill-*"))
    assert after == before  # calisma dizini temizlendi
