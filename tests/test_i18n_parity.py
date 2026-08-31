"""i18n parity and runtime tests — key sets and tr() behavior.

Tur-53: lang_tr.py and lang_en.py must contain exactly the same key sets,
and tr() must resolve every key in the current language.
"""
from __future__ import annotations

from i18n import _load_language_module, init_language, tr


def test_lang_files_have_identical_key_sets() -> None:
    tr_map = _load_language_module("tr")
    en_map = _load_language_module("en")
    assert set(tr_map) == set(en_map), (
        f"Key mismatch: only TR={sorted(set(tr_map) - set(en_map))} "
        f"only EN={sorted(set(en_map) - set(tr_map))}"
    )


def test_all_keys_nonempty_strings() -> None:
    for lang in ("tr", "en"):
        mapping = _load_language_module(lang)
        for key, value in mapping.items():
            assert isinstance(value, str) and value, f"{lang}:{key} empty"


def test_tr_resolves_every_key() -> None:
    init_language("tr")
    for key in _load_language_module("tr"):
        assert tr(key) != key, f"tr({key!r}) fell back to key"


def test_tr_falls_back_to_key_for_unknown() -> None:
    init_language("tr")
    assert tr("no.such.key") == "no.such.key"


def test_tr_placeholder_formatting() -> None:
    init_language("tr")
    result = tr("result.launch_failed", name="demo")
    assert "demo" in result
