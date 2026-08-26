"""Lock down INSERT policies for notifications and conversation_members.

Audit findings this fixes:

* notifications INSERT was ``true`` -- any authenticated user could forge
  notifications for arbitrary users. Now restricted to service-path only
  (no user context, i.e. Celery workers / backend calls).
* conversation_members INSERT was ``true`` -- any user could add themselves
  to any conversation. Now restricted to existing members or service-path.

Statements are regenerated from the updated ``app.db_rls_baseline`` so the
source of truth stays unified. Idempotent: safe to re-run.

Revision ID: 032
Revises: 031
Create Date: 2026-08-25
"""
from __future__ import annotations

from typing import Union

from alembic import op

from app.db_rls_baseline import baseline_statements, downgrade_statements

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in baseline_statements():
        op.execute(stmt)


def downgrade() -> None:
    for stmt in downgrade_statements():
        op.execute(stmt)
