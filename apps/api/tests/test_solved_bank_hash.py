"""Unit tests for solved-bank question fingerprinting (no DB needed)."""
from __future__ import annotations

import hashlib

from app.services.solved_bank import question_hash


def test_hash_is_deterministic():
    assert question_hash("Define osmosis.") == question_hash("Define osmosis.")


def test_hash_ignores_case_and_whitespace():
    assert question_hash("What is  2+2?") == question_hash("what\nis 2 + 2 ?\t")


def test_hash_ignores_smart_quote_and_dash_drift():
    a = question_hash("\u2018quoted\u2019 \u2014 dash \u2013 end")
    b = question_hash("'quoted' - dash - end")
    assert a == b


def test_hash_normalizes_multiplication_and_minus_signs():
    assert question_hash("5 \u00d7 4") == question_hash("5 x 4")
    assert question_hash("10 \u2212 3") == question_hash("10 - 3")


def test_hash_preserves_math_operators_and_decimals():
    assert question_hash("What is 2+2?") != question_hash("What is 22?")
    assert question_hash("value is 3.14") != question_hash("value is 314")
    assert question_hash("ratio 3:1") == question_hash("ratio 3:1")


def test_hash_merges_spacing_and_punctuation_noise():
    assert question_hash("State Ohm's law.") == question_hash("state ohms law")
    assert question_hash("\u2018quoted\u2019") == question_hash("quoted")


def test_hash_distinguishes_different_questions():
    assert question_hash("Define osmosis.") != question_hash("Define diffusion.")


def test_hash_matches_reference_sha256():
    expected = hashlib.sha256(b"whatis2+2").hexdigest()
    assert question_hash("What is 2 + 2?") == expected
