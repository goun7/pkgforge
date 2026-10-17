"""Stdio RPC cerceveleme testi: tek okumada gelen birden fazla satir.

Olculen (2026-10-17): `queue.add` ve `queue.start` arka arkaya (ayni pipe
paketinde) yazildiginda IKINCI istek yanitsiz kaliyordu; stdin dongusu
`select()` fd'yi bos goruyor, satir ise TextIOWrapper tamponunda bekliyordu.
Masasustu arayuzunde ikinci cagri (ve toplu kuyrugun tamam1) bir baska istek
gelene kadar takiliyordu. Bu test o durumda kirmizidir.
"""
from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _start():
    env = os.environ.copy()
    env["HOME"] = str(PROJECT_ROOT / ".tmp_home_stdio_frame")
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env=env, cwd=str(PROJECT_ROOT))


def _stop(proc: subprocess.Popen) -> None:
    try:
        proc.stdin.close()
    except OSError:
        pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _req(rid: int) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "id": rid,
                       "method": "app.version", "params": {}}).encode()


def _read_ids(proc: subprocess.Popen, want: set[int], secs: float) -> set[int]:
    """`want` id'li yanitlari en fazla `secs` boyunca topla (olaylari atlar)."""
    got: set[int] = set()
    deadline = time.time() + secs
    while want - got and time.time() < deadline:
        ready, _, _ = select.select([proc.stdout], [], [], 0.25)
        if not ready:
            continue
        line = proc.stdout.readline()
        if not line:
            break
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("id") in want:
            got.add(int(obj["id"]))
    return got


def test_tek_yazimdaki_uch_istek_de_yanitlanir() -> None:
    """Ayni chunk'a dusen satirlarin hicbiri stdin tamponunda kaybolmasin."""
    proc = _start()
    try:
        os.write(proc.stdin.fileno(), b"\n".join([_req(1), _req(2), _req(3)]) + b"\n")
        got = _read_ids(proc, {1, 2, 3}, 20)
        assert got == {1, 2, 3}, (
            f"1,2,3 beklenirken gelen {sorted(got)} — satir stdin tamponunda kaldi")
    finally:
        _stop(proc)


def test_iki_yazim_ara_sira_ayni_hizda_olsa_bile_yanitlar_donmez() -> None:
    """Ilk satir yanitini almadan ikinci satiri yaz: ikisi de cevaplanmali."""
    proc = _start()
    try:
        fd = proc.stdin.fileno()
        os.write(fd, _req(1) + b"\n")
        os.write(fd, _req(2) + b"\n")
        got = _read_ids(proc, {1, 2}, 20)
        assert got == {1, 2}, f"1,2 beklenirken gelen {sorted(got)}"
    finally:
        _stop(proc)


def test_satir_iki_parca_gelirse_tamamlanmadan_islenmez() -> None:
    """Yarım satır beklemeli, kalan parça gelince tek istek olarak işlenmeli."""
    proc = _start()
    try:
        fd = proc.stdin.fileno()
        payload = _req(7)
        os.write(fd, payload[: len(payload) // 2])
        # Yarim satir icin yanit YOK (en az 2 sn dogrula).
        early = _read_ids(proc, {7}, 2)
        assert early == set(), f"eksik satir islendi: {sorted(early)}"
        os.write(fd, payload[len(payload) // 2:] + b"\n")
        got = _read_ids(proc, {7}, 20)
        assert got == {7}, f"7 beklenirken gelen {sorted(got)}"
    finally:
        _stop(proc)
