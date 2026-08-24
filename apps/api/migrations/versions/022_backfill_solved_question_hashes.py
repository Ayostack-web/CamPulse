"""backfill solved_questions.question_hash with OCR-normalized fingerprint

The hash algorithm changed: it now normalizes unicode look-alikes and OCR
punctuation drift (smart quotes, dashes, spacing), so the same past question
scanned by two schools hashes identically. Existing rows still carry
legacy-algorithm hashes and would never collide with new ingestions.

This migration:
1. Backs up every row that will be dropped as a duplicate into
   ``solved_questions_hash_backfill_022``.
2. Deletes duplicates that collapse onto the same new fingerprint,
   preferring COMPLETED rows over QUEUED/FAILED, then the earliest row.
3. Recomputes ``question_hash`` for all surviving rows.

Downgrade restores the backed-up rows, reverts to legacy hashes and drops
the backup table.

Revision ID: 022
Revises: 021
Create Date: 2026-08-22
"""
from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.services.solved_bank import question_hash

revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | None = None
depends_on: str | None = None

_BACKUP_TABLE = "solved_questions_hash_backfill_022"


def _legacy_hash(text: str) -> str:
    """Pre-022 algorithm, needed to revert on downgrade."""
    normalized = " ".join(text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _plan(rows: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    """Pure dedup planner: returns (hash updates, duplicate ids to delete).

    ``rows`` items need ``id``, ``question_text``, ``status`` and
    ``created_at``. The keeper of each collapsed group is the row most likely
    to be servable content (COMPLETED first), then the oldest.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        new_hash = question_hash(str(row["question_text"]))
        groups.setdefault(new_hash, []).append(row)

    updates: list[dict[str, str]] = []
    delete_ids: list[str] = []
    for new_hash, members in groups.items():
        ranked = sorted(
            members,
            key=lambda r: (
                str(r.get("status")) != "COMPLETED",
                str(r.get("created_at") or ""),
                str(r["id"]),
            ),
        )
        keeper, duplicates = ranked[0], ranked[1:]
        updates.append({"id": str(keeper["id"]), "question_hash": new_hash})
        delete_ids.extend(str(d["id"]) for d in duplicates)
    return updates, delete_ids


def upgrade() -> None:
    bind = op.get_bind()

    rows = [
        dict(r)
        for r in bind.execute(
            sa.text(
                "SELECT id, question_text, status, created_at FROM solved_questions"
            )
        ).mappings()
    ]
    if not rows:
        return

    updates, delete_ids = _plan(rows)

    if delete_ids:
        bind.execute(
            sa.text(
                f"CREATE TABLE {_BACKUP_TABLE} AS "
                "SELECT * FROM solved_questions WHERE id = ANY(:ids)"
            ),
            {"ids": delete_ids},
        )
        bind.execute(
            sa.text("DELETE FROM solved_questions WHERE id = ANY(:ids)"),
            {"ids": delete_ids},
        )

    bind.execute(
        sa.text("UPDATE solved_questions SET question_hash = :h WHERE id = :id"),
        updates,
    )


def downgrade() -> None:
    bind = op.get_bind()

    has_backup = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": _BACKUP_TABLE},
    ).scalar()
    if has_backup:
        bind.execute(
            sa.text(f"INSERT INTO solved_questions SELECT * FROM {_BACKUP_TABLE}")
        )
        bind.execute(sa.text(f"DROP TABLE {_BACKUP_TABLE}"))

    rows = [
        dict(r)
        for r in bind.execute(
            sa.text("SELECT id, question_text FROM solved_questions")
        ).mappings()
    ]
    bind.execute(
        sa.text("UPDATE solved_questions SET question_hash = :h WHERE id = :id"),
        [
            {"id": str(r["id"]), "question_hash": _legacy_hash(str(r["question_text"]))}
            for r in rows
        ],
    )
