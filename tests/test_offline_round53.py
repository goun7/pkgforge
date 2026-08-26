"""Tur-53 — offline_cache tam kapsama (test-only)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import core.offline_cache as OC


@pytest.fixture()
def cache(tmp_path):
    return OC.OfflineCache(cache_dir=tmp_path / "obellek", ttl=7200)


# ── 108-117: yazma istisnasi yollari ─────────────────────────────────────────────

def test_put_json_failure_cleans_temp(cache, monkeypatch):
    cache._ensure_dir()
    cache.put("ns", "iyi", {"a": 1})
    assert cache.get("ns", "iyi") == {"a": 1}                     # saglam yol

    # json.dump patlatinca temp temizlenir ve uyarilir (108-115)
    gercek_dump = OC.json.dump

    def patlak_dump(data, f, **k):
        raise TypeError("serilestirilemez")
    monkeypatch.setattr(OC.json, "dump", patlak_dump)
    with pytest.raises(TypeError):
        cache.put("ns", "kotu", {"b": 2})
    monkeypatch.setattr(OC.json, "dump", gercek_dump)

    # os.replace hatasi -> unlink denemesi (112-114)
    cagri = {"n": 0}
    gercek_replace = OC.os.replace

    def sahte_replace(kaynak, hedef):
        if cagri["n"] == 0:
            cagri["n"] += 1
            raise OSError("rename reddi")
        return gercek_replace(kaynak, hedef)

    monkeypatch.setattr(OC.os, "replace", sahte_replace)
    cache.put("ns", "ikinci", {"c": 3})                            # 116-117


def test_put_oserror_swallowed(monkeypatch, tmp_path):
    ob = OC.OfflineCache(cache_dir=tmp_path / "dizin-yok", ttl=60)
    # _ensure_dir basarili ama yazma sirasinda dizin silinir
    def sil_dir(self):
        import shutil
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    monkeypatch.setattr(OC.OfflineCache, "_ensure_dir", sil_dir)
    ob.put("ns", "anahtar", 1)                                     # 116-117


# ── get_or_fetch: 137-152 ────────────────────────────────────────────────────────

def test_get_or_fetch_hit_miss_and_stale(cache):
    cagri = {"n": 0}

    def getir():
        cagri["n"] += 1
        if cagri["n"] == 1:
            return {"surum": "1.0"}
        raise RuntimeError("ag yok")

    # ilk: miss -> fetch -> put
    v1 = cache.get_or_fetch("paket", "x", getir)                    # 143-148
    assert v1 == {"surum": "1.0"}
    assert cagri["n"] == 1

    # ikinci: hit (139-141)
    v2 = cache.get_or_fetch("paket", "x", getir)
    assert v2 == {"surum": "1.0"} and cagri["n"] == 1

    # force_refresh + fetch patlar -> bayat deger doner (149-152)
    v3 = cache.get_or_fetch("paket", "x", getir, force_refresh=True)
    assert v3 == {"surum": "1.0"}                                   # 152

    # fetch None donerse put edilmez
    v4 = cache.get_or_fetch("paket", "bos", lambda: None, force_refresh=True)
    assert v4 is None                                               # 146-148


def test_get_or_fetch_fail_without_cache_returns_none(cache):
    def patlak():
        raise RuntimeError("ilk seferde patladi")
    sonuc = cache.get_or_fetch("paket", "yok", patlak)
    assert sonuc is None                                            # 149-152


# ── 174 / 204 / 223-237 / 247-249 ────────────────────────────────────────────────

def test_invalidate_and_clear_namespace_missing(cache, tmp_path):
    assert cache.invalidate("ns", "yok") is False                    # 160-164

    bos = tmp_path / "bos-alan"
    bos.mkdir()
    ob = OC.OfflineCache(cache_dir=bos)
    assert ob.clear_namespace("herhangi") == 0                       # 173-174


def test_stats_with_stray_file(tmp_path):
    ob = OC.OfflineCache(cache_dir=tmp_path, ttl=3600)
    ob._ensure_dir() if hasattr(ob, "_ensure_dir") else None
    ns = tmp_path / "web"
    ns.mkdir()
    (ns / "a.json").write_text(json.dumps({"v": 1}))
    (tmp_path / "gevsek.txt").write_text("dizin degil")              # 202-204
    s = ob.stats()                                                   # 196-219
    assert s["total_entries"] == 1 and s["namespaces"] == {"web": 1}
    assert s["ttl_hours"] == 1


def test_is_offline_paths(monkeypatch):
    # urlopen basarili -> False (234-235)
    class SahteYanit:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: SahteYanit())
    ob2 = OC.OfflineCache(cache_dir=Path(tempfile.mkdtemp()))
    assert ob2.is_offline() is False                                 # 235

    # urlopen patlar -> True (236-237)
    def patlak(req, timeout=0):
        raise OSError("ag kapali")
    monkeypatch.setattr("urllib.request.urlopen", patlak)
    assert ob2.is_offline() is True                                  # 236-237


def test_get_cache_singleton(monkeypatch, tmp_path):
    monkeypatch.setattr(OC, "_cache", None)

    # OfflineCache() HOME tabanli kurulus — gecici HOME ile izole et
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "obelek"))

    bir = OC.get_cache()                                             # 244-249
    iki = OC.get_cache()
    assert bir is iki                                                # singleton


# ── get TTL/hata yollari + silme aileleri ───────────────────────────────────

def test_get_expired_and_corrupt(cache):
    import time
    cache._ensure_dir()
    # suresi gecmis kayit (73-75)
    eski = cache._key_path("ns", "eski")
    eski.parent.mkdir(parents=True, exist_ok=True)
    eski.write_text(json.dumps({"_cached_at": time.time() - 99999,
                                "value": "bayat"}), encoding="utf-8")
    assert cache.get("ns", "eski") is None                        # 74-75

    # bozuk json (77-79)
    kotu = cache._key_path("ns", "kotu")
    kotu.write_text("{kesik", encoding="utf-8")
    assert cache.get("ns", "kotu") is None                        # 77-79


def test_put_temp_unlink_oserror(cache, monkeypatch):
    """113-114: temp temizligindeki ikinci hata da yutulur."""
    cache._ensure_dir()
    gercek_dump = OC.json.dump

    def patlak_dump(data, f, **k):
        raise TypeError("serilestirilemez")
    monkeypatch.setattr(OC.json, "dump", patlak_dump)

    def patlak_unlink(hedef):
        raise OSError("unlink reddi")
    monkeypatch.setattr(OC.os, "unlink", patlak_unlink)

    with pytest.raises(TypeError):
        cache.put("ns", "d", {"x": 1})
    monkeypatch.setattr(OC.json, "dump", gercek_dump)


def test_invalidate_hit_and_clear_family(cache):
    cache.put("web", "a", {"v": 1})
    cache.put("web", "b", {"v": 2})
    cache.put("app", "c", {"v": 3})

    assert cache.invalidate("web", "a") is True                    # 161-163
    assert cache.get("web", "a") is None

    assert cache.clear_namespace("web") == 1                       # 176-180
    assert cache.clear_namespace("yok-boyle") == 0                 # 173-174

    assert cache.clear_all() == 1                                   # 188-194
    assert cache.clear_all() == 0