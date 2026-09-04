"""Tests for core.bash_util PKGBUILD literal escaping."""

from __future__ import annotations

from core.bash_util import (
    bash_single_quote,
    pkgbuild_literal,
    sanitize_bash_literal,
)

# Composed to avoid embedding raw bash metacharacters in this source file.
DOLLAR_PAREN = "$" + "("
BACKTICK = chr(96)
VECTOR = DOLLAR_PAREN + "rm -rf x" + ")"


def test_plain_string_is_single_quoted():
    assert pkgbuild_literal("A simple desc") == "'A simple desc'"


def test_none_becomes_empty_literal():
    assert pkgbuild_literal(None) == "''"


def test_command_substitution_vector_stripped():
    out = pkgbuild_literal(VECTOR + " back" + BACKTICK + "tick" + BACKTICK)
    assert DOLLAR_PAREN not in out
    assert BACKTICK not in out
    assert out.startswith("'") and out.endswith("'")


def test_embedded_quote_is_escaped():
    assert bash_single_quote("it" + chr(39) + "s") == "'it'\\''s'"


def test_sanitize_keeps_safe_text():
    assert sanitize_bash_literal("cozunurluk 1920x1080 destegi") == (
        "cozunurluk 1920x1080 destegi")
