"""Full RLS coverage + FORCE, replacing the incomplete 004 baseline.

Audit findings this fixes:

* Ten tables added after 004 (ai_usage, subscriptions, referrals,
  flashcards/decks, material_unlocks, solved bank, universities,
  department_catalog) had NO row-level security at all.
* 004 defined a no-context escape hatch (``_NO_CTX``) for service paths but
  never used it in a policy; the documented worker contract was broken.
* No table used FORCE ROW LEVEL SECURITY, so any connection owning the
  tables (the default ``postgres`` role) silently bypassed every policy.

Statements are generated from ``app.db_rls_baseline`` so the migration and
the CI audit harness share one source of truth. Idempotent: safe on
environments where some of it already ran.

Revision ID: 030
Revises: 029
Create Date: 2026-08-24
"""
from __future__ import annotations

from typing import Union

from alembic import op

from app.db_rls_baseline import baseline_statements, downgrade_statements

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in baseline_statements():
        op.execute(stmt)


def downgrade() -> None:
    for stmt in downgrade_statements():
        op.execute(stmt)
