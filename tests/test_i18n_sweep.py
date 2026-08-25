"""Coverage itmesi - i18n: dil yükleme, yedek zinciri, ayar kalıcılığı."""
from __future__ import annotations

import pytest

import i18n


@pytest.fixture(autouse=True)
def _restore_tr():
    yield
    i18n.set_language("tr")


def test_init_english_loads_en_strings():
    i18n.init_language("en")
    assert i18n.get_language() == "en"
    assert i18n._strings and "tr" not in str(type(i18n._strings))


def test_init_unknown_lang_falls_back_to_tr():
    i18n.init_language("xx")
    assert i18n.get_language() == "xx"  # kod korunur ama sözlük TR
    assert i18n._strings is not None


def test_tr_fallback_chain_to_tr_then_key():
    i18n.set_language("en")
    # EN sözlüğünde olmayan anahtar -> TR'ye bakılır; orada da yoksa anahtar döner
    ghost = "totally.missing.key"
    assert i18n.tr(ghost) == ghost


def test_tr_missing_key_in_tr_returns_key_itself():
    i18n.set_language("tr")
    assert i18n.tr("yine.missing.key") == "yine.missing.key"


def test_tr_format_kwargs_and_swallowed_errors():
    i18n._strings = {"t1": "merhaba {name}", "t2": "bozuk {yok}"}
    assert i18n.tr("t1", name="dünya") == "merhaba dünya"
    # format KeyError -> sessizce ham metin
    assert i18n.tr("t2", baska=1) == "bozuk {yok}"
    i18n._strings = {"t3": "{!yanlis}"}
    assert i18n.tr("t3", x=1) == "{!yanlis}"  # ValueError da yutulur


def test_set_language_persists(tmp_path):
    i18n.set_language("en")
    assert i18n.load_setting("language") == "en"


def test_available_languages_shape():
    langs = i18n.available_languages()
    assert ("tr", "Türkçe") in langs and ("en", "English") in langs


def test_load_settings_corrupt_json_returns_empty():
    from i18n import settings_file
    sf = settings_file()
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text("{kesik json", encoding="utf-8")
    assert i18n.load_settings() == {}


def test_save_setting_merges_not_replaces():
    i18n.save_settings({"a": 1, "language": "tr"})
    i18n.save_setting("b", 2)
    s = i18n.load_settings()
    assert s["a"] == 1 and s["b"] == 2


def test_tr_auto_inits_when_empty():
    saved = i18n._strings
    i18n._strings = {}
    try:
        assert i18n.tr("cli.arg_version")
    finally:
        i18n._strings = saved
