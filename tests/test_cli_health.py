"""Coverage itmesi — cli list ve health raporlari."""
from __future__ import annotations

from types import SimpleNamespace as NS

import cli


def _rec(idx, status="installed", name="demo", ptype="deb", ts="2025-01-01"):
    return NS(id=idx, timestamp=ts, package_name=name, package_type=ptype,
              status=status, original_file=f"{name}.pkg.tar.zst", backup_pkg=None)


class FakeDB:
    def __init__(self, records, stats):
        self._records = records
        self._stats = stats

    def get_history(self, limit=50):
        return self._records[:limit]

    def get_records_for_package(self, name):
        return [r for r in self._records if r.package_name == name]

    def get_usage_stats(self):
        return self._stats


def _stats(total, installed, converted, failed, types=None, archs=None,
           url=0, avg=0.0):
    return {
        "total": total,
        "by_status": {"installed": installed, "converted": converted,
                      "install_failed": failed},
        "by_type": types or {},
        "by_arch": archs or {},
        "url_count": url,
        "avg_output_size_mb": avg,
    }


def test_cmd_list_empty(capsys, monkeypatch):
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB([], {}))
    rc = cli._cmd_list(NS())
    out = capsys.readouterr().out
    assert rc == 0 and "bulunmuyor" in out.lower()


def test_cmd_list_rows(capsys, monkeypatch):
    recs = [_rec(1), _rec(2, status="install_failed", name="kırık")]
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB(recs, {}))
    rc = cli._cmd_list(NS())
    out = capsys.readouterr().out
    assert rc == 0 and "demo" in out and "kırık" in out


def test_health_empty(capsys, monkeypatch):
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB([], _stats(0, 0, 0, 0)))
    rc = cli._cmd_health(NS())
    out = capsys.readouterr().out
    assert rc == 0 and "bulunmuyor" in out


def _rich(monkeypatch, capsys, installed, converted, failed, extra=None):
    recs = [_rec(i, name=f"p{i % 3}") for i in range(installed + converted)]
    recs += [_rec(100 + i, status="install_failed", name=f"hata{i}")
             for i in range(failed)]
    stats = _stats(len(recs), installed, converted, failed,
                   types={"deb": 8, "rpm": 2}, archs={"x86_64": 9, "any": 1},
                   url=3, avg=12.5)
    if extra:
        stats.update(extra)
        recs = [recs[0]] * 2 + recs
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB(recs, stats))
    rc = cli._cmd_health(NS())
    return rc, capsys.readouterr().out


def test_health_perfect(capsys, monkeypatch):
    rc, out = _rich(monkeypatch, capsys, 10, 0, 0)
    assert rc == 0
    assert "Mükemmel" in out and "Son Aktivite" in out
    assert "deb" in out and "x86_64" in out and "12.5 MB" in out


def test_health_good_and_troubled(capsys, monkeypatch):
    rc, out = _rich(monkeypatch, capsys, 7, 1, 2)
    assert rc == 0 and "İyi" in out and "Başarısız Paketler" in out
    assert "hata0" in out

    rc2, out2 = _rich(monkeypatch, capsys, 3, 0, 7)
    assert rc2 == 0 and "Sorunlu" in out2


def test_health_top_packages(capsys, monkeypatch):
    recs = [_rec(i, name="ayni") for i in range(4)]
    stats = _stats(4, 4, 0, 0)
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB(recs, stats))
    rc = cli._cmd_health(NS())
    out = capsys.readouterr().out
    assert rc == 0 and "En Çok Dönüşen" in out and "ayni: 4 kez" in out
