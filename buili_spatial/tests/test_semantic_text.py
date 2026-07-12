from __future__ import annotations

from buili_spatial.semantic_auto import _dimension_text


def test_dimension_parser_handles_typographic_primes() -> None:
    assert _dimension_text("12′-6″ x 10’-0”") == "12'-6\" x 10'-0\""


def test_dimension_parser_rejects_implausible_inches() -> None:
    assert _dimension_text("12'-19\" x 10'-0\"") == ""
