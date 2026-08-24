"""Faz 5 (F5.25) — upstream enrichment: otomatik description doldurma."""
from __future__ import annotations

from core.from_source import _detect_description, generate_pkgbuild_from_source


def test_description_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        chr(10).join(["[project]", 'name = "x"',
                      'description = "A pyproject desc"']))
    assert _detect_description(tmp_path, "x") == "A pyproject desc"


def test_description_from_cargo(tmp_path):
    (tmp_path / "Cargo.toml").write_text(
        chr(10).join(["[package]", 'name = "x"',
                      'description = "A cargo desc"']))
    assert _detect_description(tmp_path, "x") == "A cargo desc"


def test_description_from_package_json(tmp_path):
    (tmp_path / "package.json").write_text(
        '{ "name": "x", "description": "A node desc" }')
    assert _detect_description(tmp_path, "x") == "A node desc"


def test_description_from_readme_fallback(tmp_path):
    (tmp_path / "README.md").write_text(
        chr(10).join(["# Title", "", "This is a long enough readme line."]))
    assert _detect_description(tmp_path, "x") == \
        "This is a long enough readme line."


def test_description_default_fallback(tmp_path):
    assert _detect_description(tmp_path, "mypkg") == \
        "mypkg — kaynaktan derlenen paket"


def test_pyproject_takes_priority_over_readme(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        chr(10).join(["[project]", 'description = "Manifest wins"']))
    (tmp_path / "README.md").write_text(
        chr(10).join(["This is a long enough readme line."]))
    assert _detect_description(tmp_path, "x") == "Manifest wins"


def test_generate_pkgbuild_uses_enriched_description(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        chr(10).join(["[project]", 'name = "demo"', 'version = "1.2.3"',
                      'description = "Enriched demo description"']))
    out = generate_pkgbuild_from_source(
        "demo", "https://example.com/demo.git", "python", tmp_path)
    assert "Enriched demo description" in out
    assert "pkgver=1.2.3" in out
