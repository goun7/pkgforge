"""pkgforge core.doctor dal-kesen testleri (LEED) — 6 prob fonksiyonu.

Kapsanan fonksiyonlar: _check_tools, _check_polkit, _check_keyring,
_check_storage, _check_dbus, _check_scheduler.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — discover_tools/secrets_store/dbus_service/scheduler
         MONKEYPATCH; /usr/share yol kontrolleri Path.is_file stub ile;
         depolama tmp_path'e yonlendirildi (network/DB YOK).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, ".")
import core.dbus_service  # noqa: E402
import core.doctor  # noqa: E402
import core.privileged  # noqa: E402
import core.scheduler  # noqa: E402
import core.secrets_store  # noqa: E402
from core.doctor import (  # noqa: E402
    _check_dbus, _check_keyring, _check_polkit, _check_scheduler,
    _check_storage, _check_tools,
)

_POLICY = "/usr/share/polkit-1/actions/org.pkgforge.helper.policy"
_HELPER = "/usr/share/pkgforge/scripts/pkgforge-privileged.sh"


class _ToolsShim:
    """discover_tools() yerine gecer — Tools veri-yapisinin alanlari."""

    def __init__(self, missing_required=(), missing_optional=(), debtap=False,
                 pkexec=False, distrobox=False):
        self.missing_required = list(missing_required)
        self.missing_optional = list(missing_optional)
        self.debtap = debtap
        self.pkexec = pkexec
        self.has_distrobox = distrobox


def _patch_isfile(monkeypatch, existing):
    """Path.is_file -> uzvluk kontrolu (gercek /usr/share erisimi YOK)."""
    existing = set(existing)
    monkeypatch.setattr(Path, "is_file", lambda self: str(self) in existing)


# == _check_tools ==================================================================================

@pytest.mark.parametrize("missing_req,expected_ok", [
    ([], True),
    (["debtap"], False),
    (["debtap", "pkexec"], False),
])
def test_tools_missing_required(monkeypatch, missing_req, expected_ok):
    """ORTAM: ok = missing_required YOK (zorunlu araclar)."""
    monkeypatch.setattr(core.doctor, "discover_tools",
                        lambda: _ToolsShim(missing_required=missing_req))
    r = _check_tools()
    assert r["ok"] is expected_ok
    assert r["missing_required"] == missing_req


def test_tools_eksik_listesi_aktarilir(monkeypatch):
    """ORTAM: missing_required/optional listeleri birebir aktarilir."""
    monkeypatch.setattr(core.doctor, "discover_tools",
                        lambda: _ToolsShim(missing_required=["a"], missing_optional=["b", "c"]))
    r = _check_tools()
    assert r["missing_required"] == ["a"]
    assert r["missing_optional"] == ["b", "c"]


@pytest.mark.parametrize("debtap,pkexec,distrobox", [
    (True, True, True),
    (False, False, False),
    (True, False, True),
])
def test_tools_arac_bayraklari_bool(monkeypatch, debtap, pkexec, distrobox):
    """ORTAM: debtap/pkexec bool'e cast; distrobox has_distrobox'tan."""
    monkeypatch.setattr(core.doctor, "discover_tools",
                        lambda: _ToolsShim(debtap=debtap, pkexec=pkexec,
                                           distrobox=distrobox))
    r = _check_tools()
    assert r["debtap"] is debtap
    assert r["pkexec"] is pkexec
    assert r["distrobox"] is distrobox


def test_tools_anahtarlar_tam(monkeypatch):
    """ORTAM: donus anahtar seti sabittir."""
    monkeypatch.setattr(core.doctor, "discover_tools", lambda: _ToolsShim())
    assert set(_check_tools().keys()) == {
        "ok", "missing_required", "missing_optional", "debtap", "pkexec",
        "distrobox"}


def test_tools_missing_optional_ok_i_bozmaz(monkeypatch):
    """ORTAM: sadece opsiyonel eksiklik ok=True korur."""
    monkeypatch.setattr(core.doctor, "discover_tools",
                        lambda: _ToolsShim(missing_optional=["distrobox"]))
    assert _check_tools()["ok"] is True


# == _check_polkit =================================================================================

def test_polkit_policy_kurulu_degil(monkeypatch):
    """ORTAM: policy yok -> ok False + 'policy kurulu değil' detayi."""
    _patch_isfile(monkeypatch, {_HELPER})
    monkeypatch.setattr(core.privileged, "PRIVILEGED_HELPER", Path(_HELPER))
    r = _check_polkit()
    assert r["ok"] is False
    assert r["policy_installed"] is False
    assert r["helper_installed"] is True
    assert r["running_from_source"] is False
    assert "policy kurulu değil" in r["detail"]


def test_polkit_kaynaktan_calisma(monkeypatch):
    """ORTAM: policy var ama /usr/share disinda -> 'Kaynak ağacından'."""
    _patch_isfile(monkeypatch, {_POLICY, _HELPER})
    monkeypatch.setattr(core.privileged, "PRIVILEGED_HELPER",
                        Path("/home/user/pkgforge/scripts/pkgforge-privileged.sh"))
    r = _check_polkit()
    assert r["ok"] is False
    assert r["policy_installed"] is True
    assert r["running_from_source"] is True
    assert "Kaynak ağacından" in r["detail"]


def test_polkit_helper_kurulu_degil(monkeypatch):
    """ORTAM: policy + sistem yolu ama helper yok -> 'install.sh ile kurun'."""
    _patch_isfile(monkeypatch, {_POLICY})
    monkeypatch.setattr(core.privileged, "PRIVILEGED_HELPER", Path(_HELPER))
    r = _check_polkit()
    assert r["ok"] is False
    assert r["helper_installed"] is False
    assert r["running_from_source"] is False
    assert "install.sh ile kurun" in r["detail"]


def test_polkit_tamam(monkeypatch):
    """ORTAM: policy + helper + sistem yolu -> ok True, detail bos."""
    _patch_isfile(monkeypatch, {_POLICY, _HELPER})
    monkeypatch.setattr(core.privileged, "PRIVILEGED_HELPER", Path(_HELPER))
    r = _check_polkit()
    assert r["ok"] is True
    assert r["detail"] == ""


@pytest.mark.parametrize("helper_path,from_source", [
    ("/usr/share/pkgforge/scripts/pkgforge-privileged.sh", False),
    ("/usr/local/share/pkgforge/scripts/pkgforge-privileged.sh", True),
    ("/home/gokun/projects/pkgforge/scripts/pkgforge-privileged.sh", True),
    ("/usr/share/pkgforge-other/x.sh", True),
])
def test_polkit_running_from_source(monkeypatch, helper_path, from_source):
    """ORTAM: running_from_source = helper '/usr/share/pkgforge/' ile BASLAMIYORSA."""
    _patch_isfile(monkeypatch, {_POLICY, _HELPER})
    monkeypatch.setattr(core.privileged, "PRIVILEGED_HELPER", Path(helper_path))
    r = _check_polkit()
    assert r["running_from_source"] is from_source


def test_polkit_policy_oncelikli_detay(monkeypatch):
    """ORTAM: policy yoksa kaynak/helper detaylari BASILMAZ (once policy)."""
    _patch_isfile(monkeypatch, set())  # ikisi de yok
    monkeypatch.setattr(core.privileged, "PRIVILEGED_HELPER",
                        Path("/home/x/pkgforge/scripts/pkgforge-privileged.sh"))
    r = _check_polkit()
    assert r["policy_installed"] is False
    assert "Kaynak ağacından" not in r["detail"]
    assert "install.sh ile kurun" not in r["detail"]


def test_polkit_anahtarlar_tam(monkeypatch):
    """ORTAM: donus anahtar seti sabittir."""
    _patch_isfile(monkeypatch, {_POLICY, _HELPER})
    monkeypatch.setattr(core.privileged, "PRIVILEGED_HELPER", Path(_HELPER))
    assert set(_check_polkit().keys()) == {
        "ok", "policy_installed", "helper_installed", "running_from_source",
        "detail"}


# == _check_keyring ================================================================================

def test_keyring_erisilebilir(monkeypatch):
    """ORTAM: available() True -> ok True + Secret Service detayi."""
    monkeypatch.setattr(core.secrets_store, "available", lambda: True)
    r = _check_keyring()
    assert r["ok"] is True
    assert "Secret Service erisilebilir" in r["detail"]


def test_keyring_yok(monkeypatch):
    """ORTAM: available() False -> ok False + 'devre disi'."""
    monkeypatch.setattr(core.secrets_store, "available", lambda: False)
    r = _check_keyring()
    assert r["ok"] is False
    assert "Secret Service yok" in r["detail"]


@pytest.mark.parametrize("truthy", [1, "yes", [1], object()])
def test_keyring_truthy_degerler_ok(monkeypatch, truthy):
    """ORTAM: available() truthy-false deger -> bool(True)."""
    monkeypatch.setattr(core.secrets_store, "available", lambda: truthy)
    assert _check_keyring()["ok"] is True


@pytest.mark.parametrize("falsy", [0, "", None, [], {}])
def test_keyring_falsy_degerler_degil(monkeypatch, falsy):
    """ORTAM: available() falsy -> bool(False)."""
    monkeypatch.setattr(core.secrets_store, "available", lambda: falsy)
    assert _check_keyring()["ok"] is False


def test_keyring_istisna_zarif_duser(monkeypatch):
    """ORTAM: available() exception -> ok False + 'sorgulanamadi' (crash YOK)."""
    def boom():
        raise RuntimeError("dbus yok")

    monkeypatch.setattr(core.secrets_store, "available", boom)
    r = _check_keyring()
    assert r["ok"] is False
    assert "anahtarlik sorgulanamadi" in r["detail"]
    assert "dbus yok" in r["detail"]


# == _check_storage ================================================================================

def test_storage_gecerli_klasor(monkeypatch, tmp_path):
    """ORTAM: config klasoru + db'ler var -> hepsi exists True."""
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    hist = tmp_path / "h.db"
    hist.write_text("")
    qdb = tmp_path / "q.db"
    qdb.write_text("")
    monkeypatch.setattr(core.doctor, "CONFIG_DIR", cfg)
    monkeypatch.setattr(core.doctor, "history_db_path", lambda: hist)
    monkeypatch.setattr(core.doctor, "queue_db_path", lambda: qdb)
    monkeypatch.setattr(core.doctor, "get_active_profile", lambda: "test")
    r = _check_storage()
    assert r["ok"] is True
    assert r["config_dir"] == str(cfg)
    assert r["config_dir_exists"] is True
    assert r["profile"] == "test"
    assert r["history_db"] == str(hist)
    assert r["history_db_exists"] is True
    assert r["queue_db"] == str(qdb)
    assert r["queue_db_exists"] is True


def test_storage_eksik_klasor(monkeypatch, tmp_path):
    """ORTAM: hicbir sey yoksa exists bayraklari False (ok yine True)."""
    cfg = tmp_path / "yok"
    monkeypatch.setattr(core.doctor, "CONFIG_DIR", cfg)
    monkeypatch.setattr(core.doctor, "history_db_path", lambda: tmp_path / "h.db")
    monkeypatch.setattr(core.doctor, "queue_db_path", lambda: tmp_path / "q.db")
    monkeypatch.setattr(core.doctor, "get_active_profile", lambda: "default")
    r = _check_storage()
    assert r["ok"] is True  # storage her zaman ok (best-effort prob)
    assert r["config_dir_exists"] is False
    assert r["history_db_exists"] is False
    assert r["queue_db_exists"] is False


def test_storage_kismi(monkeypatch, tmp_path):
    """ORTAM: sadece config klasoru varsa sadece o True."""
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setattr(core.doctor, "CONFIG_DIR", cfg)
    monkeypatch.setattr(core.doctor, "history_db_path", lambda: cfg / "h.db")
    monkeypatch.setattr(core.doctor, "queue_db_path", lambda: cfg / "q.db")
    monkeypatch.setattr(core.doctor, "get_active_profile", lambda: "p")
    r = _check_storage()
    assert r["config_dir_exists"] is True
    assert r["history_db_exists"] is False
    assert r["queue_db_exists"] is False


@pytest.mark.parametrize("profile", ["default", "gaming", "server", "x"])
def test_storage_profil_aktarilir(monkeypatch, tmp_path, profile):
    """ORTAM: get_active_profile degeri rapora gecer."""
    monkeypatch.setattr(core.doctor, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(core.doctor, "history_db_path", lambda: tmp_path / "h")
    monkeypatch.setattr(core.doctor, "queue_db_path", lambda: tmp_path / "q")
    monkeypatch.setattr(core.doctor, "get_active_profile", lambda: profile)
    assert _check_storage()["profile"] == profile


def test_storage_anahtarlar_tam(monkeypatch, tmp_path):
    """ORTAM: donus anahtar seti sabittir."""
    monkeypatch.setattr(core.doctor, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(core.doctor, "history_db_path", lambda: tmp_path / "h")
    monkeypatch.setattr(core.doctor, "queue_db_path", lambda: tmp_path / "q")
    monkeypatch.setattr(core.doctor, "get_active_profile", lambda: "d")
    assert set(_check_storage().keys()) == {
        "ok", "config_dir", "config_dir_exists", "profile", "history_db",
        "history_db_exists", "queue_db", "queue_db_exists"}


# == _check_dbus ===================================================================================

def test_dbus_mevcut(monkeypatch):
    """ORTAM: service_status available True -> ok True."""
    monkeypatch.setattr(core.dbus_service, "service_status",
                        lambda: {"available": True, "running": True, "bus_name": "o.p.A"})
    r = _check_dbus()
    assert r["ok"] is True
    assert r["detail"]["available"] is True
    assert r["detail"]["bus_name"] == "o.p.A"


def test_dbus_degil(monkeypatch):
    """ORTAM: available False -> ok False."""
    monkeypatch.setattr(core.dbus_service, "service_status",
                        lambda: {"available": False})
    assert _check_dbus()["ok"] is False


@pytest.mark.parametrize("st", [{"available": True}, {"available": "x"},
                                {"available": 1}, {"available": [1]}])
def test_dbus_truthy_ok(monkeypatch, st):
    """ORTAM: available truthy -> ok True (bool cast)."""
    monkeypatch.setattr(core.dbus_service, "service_status", lambda: st)
    assert _check_dbus()["ok"] is True


@pytest.mark.parametrize("st", [{}, {"available": None}, {"available": 0},
                                {"available": ""}, {"x": 1}])
def test_dbus_falsy_eksik_ok_degil(monkeypatch, st):
    """ORTAM: available falsy/eksik -> ok False (get default False)."""
    monkeypatch.setattr(core.dbus_service, "service_status", lambda: st)
    assert _check_dbus()["ok"] is False


def test_dbus_istisna_zarif_duser(monkeypatch):
    """ORTAM: service_status exception -> ok False (crash YOK)."""
    def boom():
        raise OSError("bus yok")

    monkeypatch.setattr(core.dbus_service, "service_status", boom)
    r = _check_dbus()
    assert r["ok"] is False
    assert "dbus durumu okunamadi" in r["detail"]
    assert "bus yok" in r["detail"]


# == _check_scheduler ==============================================================================

def test_scheduler_ok(monkeypatch):
    """ORTAM: TASKS + state ok -> ok True + tasks sayisi."""
    monkeypatch.setattr(core.scheduler, "TASKS", ["a", "b", "c"])
    monkeypatch.setattr(core.scheduler, "state",
                        lambda: {"enabled": True, "interval_hours": 12.0})
    r = _check_scheduler()
    assert r["ok"] is True
    assert r["tasks"] == 3
    assert r["state"]["enabled"] is True


@pytest.mark.parametrize("tasks,expected", [
    ([], 0), (["a"], 1), (["a", "b", "c", "d"], 4),
])
def test_scheduler_tasks_sayisi(monkeypatch, tasks, expected):
    """ORTAM: len(TASKS) rapor edilir."""
    monkeypatch.setattr(core.scheduler, "TASKS", tasks)
    monkeypatch.setattr(core.scheduler, "state", lambda: {})
    assert _check_scheduler()["tasks"] == expected


def test_scheduler_istisna_zarif_duser(monkeypatch):
    """ORTAM: state exception -> ok False (crash YOK)."""
    def boom():
        raise RuntimeError("scheduler yok")

    monkeypatch.setattr(core.scheduler, "TASKS", [])
    monkeypatch.setattr(core.scheduler, "state", boom)
    r = _check_scheduler()
    assert r["ok"] is False
    assert "zamanlayici okunamadi" in r["detail"]
    assert "scheduler yok" in r["detail"]


def test_scheduler_state_aktarilir(monkeypatch):
    """ORTAM: state() donusu oldugu gibi aktarilir."""
    st = {"enabled": False, "interval_hours": 24.0, "task": "check_updates"}
    monkeypatch.setattr(core.scheduler, "TASKS", ["t"])
    monkeypatch.setattr(core.scheduler, "state", lambda: st)
    assert _check_scheduler()["state"] == st
