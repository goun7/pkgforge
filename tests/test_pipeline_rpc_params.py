"""pipeline.start RPC'sinin 'install' ve 'out_dir' parametreleri (2026-10-17).

Olculen bug: handle_pipeline_start bu iki parametreyi sessizce yutuyordu.
Sonuc:
  1. 'install': false verilmesine ragmen pipeline kurulum adimina girip
     Polkit yukseltme istiyordu (olcum: 9 Polkit log'u).
  2. 'out_dir': paket istenen hedefe degil, yalnizca girdinin bulundugu
     dizine birakiliyordu.

queue.add (handlers_queue.py::_make_pipeline) bu davranislari zaten dogru
uyguluyordu; bu testler ayni kurallarin tek-dosya yolunda da uygulandigini
kanitlar. Kirmizi kanit uretildi: duzeltme geri alininca her iki test de
fail veriyor.

Not: canli_* testleri gercek sidecar surecini (main.py serve) kaldirir ve
gercek .deb'i (utest/hello_1.0.0-1_amd64.deb) donusturur. Gecici HOME ve
gecici out_dir kullanilir; kullanici makinesine dokunmaz.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

import core.api_server as AS

REPO = Path(__file__).resolve().parent.parent
GERCEK_DEB = REPO / "utest" / "hello_1.0.0-1_amd64.deb"


@pytest.fixture()
def senkron(monkeypatch):
    """Olaylari kayda al, thread'i senkron calistir."""
    olaylar = []
    monkeypatch.setattr(AS.transport, "_event",
                        lambda m, p: olaylar.append((m, p)))
    return olaylar


class _SahteBoru:
    """handle_pipeline_start'in parametre aktarimini olcen sahte pipeline.

    Gercek donusum degil, yalnizca hangi parametrelerin ulastigini kayda
    alir: set_output_dir cagri mi, _skip_install_message dolu mu.
    """

    def __init__(self):
        self.step_changed = _Sig()
        self.progress = _Sig()
        self.log_message = _Sig()
        self.compatibility_ready = _Sig()
        self.finished = _Sig()
        self.output_dir = None
        self.skip_mesaj = ""

    def set_output_dir(self, directory: Path) -> None:
        self.output_dir = directory

    def stage(self, p, forced=None):
        pass

    def run_staged(self):
        pass

    @property
    def _skip_install_message(self) -> str:
        return self.skip_mesaj

    @_skip_install_message.setter
    def _skip_install_message(self, deger: str) -> None:
        self.skip_mesaj = deger


class _Sig:
    def __init__(self):
        self._cbs = []

    def connect(self, cb, **kw):
        self._cbs.append(cb)

    def emit(self, *a, **kw):
        for cb in list(self._cbs):
            cb(*a, **kw)


def _sahte_kur(monkeypatch, tmp_path):
    import sys
    from types import SimpleNamespace as NS

    boru = _SahteBoru()
    monkeypatch.setitem(sys.modules, "core.pipeline",
                        NS(ConversionPipeline=lambda *a, **k: boru))
    return boru


def test_install_false_atlamayı_setler(monkeypatch, tmp_path, senkron):
    """install=false -> _skip_install_message dolu gelir; kapi beklenmez."""
    boru = _sahte_kur(monkeypatch, tmp_path)
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")
    yanit = AS.handle_pipeline_start({"path": str(deb), "install": False})
    assert yanit["started"] is True
    assert boru.skip_mesaj, (
        "install=false verildi ama _skip_install_message bos — pipeline "
        "yine kurulum adimina girecek ve Polkit isteyecektir.")
    assert boru.output_dir is None  # out_dir verilmedi: varsayilan


def test_out_dir_hedefe_aktarilir(monkeypatch, tmp_path, senkron):
    """out_dir -> set_output_dir ile pipeline'a ulasir."""
    boru = _sahte_kur(monkeypatch, tmp_path)
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")
    hedef = tmp_path / "cikti"
    AS.handle_pipeline_start(
        {"path": str(deb), "out_dir": str(hedef), "install": False})
    assert boru.output_dir == hedef, (
        "out_dir parametresi pipeline'a ulasmadi — paket istenen hedefe "
        "degil girdinin yanina birakilacak.")


def test_install_true_skip_mesaji_birakmaz(monkeypatch, tmp_path, senkron):
    """install=true (acente onayi) -> skip mesaji bos kalmali."""
    boru = _sahte_kur(monkeypatch, tmp_path)
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")
    AS.handle_pipeline_start({"path": str(deb), "install": True})
    assert boru.skip_mesaj == ""


def test_settings_output_dir_out_dir_verilmezse_kullanilir(monkeypatch, tmp_path, senkron):
    """out_dir parametresi yoksa kayitli 'output_dir' ayari kullanilir.

    Olculen bulgu (2026-10-17): Settings sayfasindaki "urun dizini" alani
    tamamen olu idi — kaydediliyor ama donusum yolu hic okumuyordu; paket
    her zaman girdinin yanina birakiliyordu.
    """
    import i18n

    boru = _sahte_kur(monkeypatch, tmp_path)
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")
    hedef = tmp_path / "ayar_hedefi"
    monkeypatch.setattr(i18n, "load_setting",
                        lambda anahtar, varsayilan=None: (
                            str(hedef) if anahtar == "output_dir" else varsayilan))
    AS.handle_pipeline_start({"path": str(deb), "install": False})
    assert boru.output_dir == hedef, (
        "kayitli output_dir ayari pipeline'a ulasmadi — Settings'teki alan "
        "hala kullanilmiyor demektir.")


def test_settings_output_dir_bossa_varsayilan_gecerli(monkeypatch, tmp_path, senkron):
    """Ayar bossa out_dir None kalmali (cli.py:158: urun girisin yanina)."""
    import i18n

    boru = _sahte_kur(monkeypatch, tmp_path)
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")
    monkeypatch.setattr(i18n, "load_setting",
                        lambda anahtar, varsayilan=None: varsayilan)
    AS.handle_pipeline_start({"path": str(deb), "install": False})
    assert boru.output_dir is None


def test_explicit_out_dir_settings_ezilir(monkeypatch, tmp_path, senkron):
    """Explicit out_dir parametresi kayitli ayarin onunde gelir."""
    import i18n

    boru = _sahte_kur(monkeypatch, tmp_path)
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")
    ayar_hedef = tmp_path / "ayar_hedefi"
    param_hedef = tmp_path / "param_hedefi"
    monkeypatch.setattr(i18n, "load_setting",
                        lambda anahtar, varsayilan=None: (
                            str(ayar_hedef) if anahtar == "output_dir" else varsayilan))
    AS.handle_pipeline_start(
        {"path": str(deb), "out_dir": str(param_hedef), "install": False})
    assert boru.output_dir == param_hedef


# --- canli surec testleri (gercek sidecar + gercek .deb) ---------------------

def _sidecar_baslat():
    home = tempfile.mkdtemp(prefix="pf_rpc_home_")
    env = dict(os.environ)
    env["HOME"] = home
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [str(REPO / ".venv/bin/python"), "main.py", "serve"],
        cwd=str(REPO), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env=env, bufsize=1)
    return proc, home


@pytest.mark.skipif(not GERCEK_DEB.is_file(),
                    reason="utest/hello_1.0.0-1_amd64.deb yok")
def test_canli_install_false_polkit_stemiyor(tmp_path):
    """Gercek sidecar: install=false ile kurulum adimi atlanir.

    Olculen (2026-10-17, duzeltme oncesi): 9 'Polkit' log'u + step 5
    'running' + 'Paket kuruluyor'. Duzeltme sonrasi: step 5 'skipped',
    Polkit log sayisi 0, success=true.
    """
    proc, _home = _sidecar_baslat()
    try:
        olaylar = _topla(proc)
        time.sleep(2.5)
        deb = GERCEK_DEB.resolve()
        out = Path(tempfile.mkdtemp(prefix="pf_rpc_out_"))
        _rpc(proc, "pipeline.start",
             {"path": str(deb), "out_dir": str(out), "install": False})
        _bekle(proc, olaylar, "event/finished", timeout=90)
    finally:
        _kapat(proc)
    loglar = [str(p.get("message", "")) for m, p in olaylar
              if m == "event/log"]
    adimlar = [(p.get("step"), p.get("status")) for m, p in olaylar
               if m == "event/step_changed"]
    polkit = [l for l in loglar if "Polkit" in l]
    fin = [p for m, p in olaylar if m == "event/finished"]
    assert polkit == [], (
        f"install=false verilmesine ragmen {len(polkit)} Polkit log'u "
        f"var: {polkit[:3]}")
    assert (5, "skipped") in adimlar, (
        f"step 5 'skipped' olmali, got {adimlar}")
    assert fin and fin[-1]["success"] is True, (
        f"convert-only yol success=true olmali, got {fin}")


@pytest.mark.skipif(not GERCEK_DEB.is_file(),
                    reason="utest/hello_1.0.0-1_amd64.deb yok")
def test_canli_out_dir_paketi_istenen_yere_koyar(tmp_path):
    """Gercek sidecar: out_dir parametresi paketin yerini belirler.

    Olculen (2026-10-17, duzeltme oncesi): paket out_dir'e degil girdinin
    dizinine (repo/utest/) birakiliyordu. Duzeltme sonrasi: output_pkg
    istenen out_dir icinde.
    """
    proc, _home = _sidecar_baslat()
    try:
        olaylar = _topla(proc)
        time.sleep(2.5)
        deb = GERCEK_DEB.resolve()
        out = Path(tempfile.mkdtemp(prefix="pf_rpc_out_"))
        _rpc(proc, "pipeline.start",
             {"path": str(deb), "out_dir": str(out), "install": False})
        _bekle(proc, olaylar, "event/finished", timeout=90)
    finally:
        _kapat(proc)
    fin = [p for m, p in olaylar if m == "event/finished"]
    assert fin, "event/finished gelmedi"
    output_pkg = Path(fin[-1]["output_pkg"])
    assert output_pkg.is_file(), (
        f"output_pkg bir dosya olmali: {output_pkg}")
    assert output_pkg.parent == out, (
        f"paket istenen out_dir icinde degil: {output_pkg} (istedik: {out})")
    assert output_pkg.stat().st_size > 0


# --- yardimcilar ---------------------------------------------------------------

def _topla(proc) -> list:
    olaylar: list[tuple[str, object]] = []
    lock = threading.Lock()

    def oku():
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line)
            except json.JSONDecodeError:
                continue
            idv = v.get("id")
            if isinstance(idv, int):
                with lock:
                    _yanitlar[v.get("id", -1)] = v
            else:
                m = v.get("method")
                if isinstance(m, str):
                    with lock:
                        olaylar.append((m, v.get("params")))

    _yanitlar.clear()
    threading.Thread(target=oku, daemon=True).start()
    return olaylar


_yanitlar: dict[int, dict] = {}


def _rpc(proc, method: str, params: dict, timeout: float = 30) -> dict:
    rid = len(_yanitlar) + 1
    proc.stdin.write(json.dumps(
        {"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        + "\n")
    proc.stdin.flush()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if rid in _yanitlar:
            return _yanitlar[rid]
        time.sleep(0.05)
    raise TimeoutError(method)


def _bekle(proc, olaylar, hedef: str, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(m == hedef for m, _ in olaylar):
            return
        time.sleep(0.5)


def _kapat(proc) -> None:
    try:
        proc.stdin.close()
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
