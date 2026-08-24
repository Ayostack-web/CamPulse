"""Unit tests for migration 022's dedup planner (no DB needed)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from app.services.solved_bank import question_hash


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "022_backfill_solved_question_hashes.py"
    )
    spec = importlib.util.spec_from_file_location("mig022", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


def _row(id_: str, text: str, status: str = "COMPLETED", created: str = "2026-01-01"):
    return {"id": id_, "question_text": text, "status": status, "created_at": created}


def test_identical_questions_collapse_with_completed_keeper():
    mig = _load_migration()
    rows = [
        _row("a", "Define osmosis.", status="QUEUED"),
        _row("b", "define  OSMOSIS.", status="COMPLETED"),
        _row("c", "Define osmosis.", status="FAILED"),
    ]
    updates, deletes = mig._plan(rows)
    assert [u["id"] for u in updates] == ["b"]
    assert sorted(deletes) == ["a", "c"]
    assert updates[0]["question_hash"] == question_hash("Define osmosis.")


def test_same_status_keeps_oldest_row():
    mig = _load_migration()
    rows = [
        _row("late", "State Ohm's law.", created="2026-03-01"),
        _row("early", "state ohms law", created="2026-01-01"),
    ]
    updates, deletes = mig._plan(rows)
    assert [u["id"] for u in updates] == ["early"]
    assert deletes == ["late"]


def test_distinct_rows_all_get_updates_no_deletes():
    mig = _load_migration()
    rows = [_row("a", "What is 2+2?"), _row("b", "What is 22?")]
    updates, deletes = mig._plan(rows)
    assert len(updates) == 2
    assert deletes == []


def test_new_hashes_differ_from_legacy_algorithm():
    mig = _load_migration()
    text = "What is 2 + 2?"
    rows = [_row("a", text)]
    updates, deletes = mig._plan(rows)
    assert deletes == []
    assert updates[0]["question_hash"] != mig._legacy_hash(text)


def test_legacy_hash_matches_pre_022_behaviour():
    mig = _load_migration()
    import hashlib

    expected = hashlib.sha256(b"what is 2 + 2?").hexdigest()
    assert mig._legacy_hash("  What\nis 2 + 2?  ") == expected
