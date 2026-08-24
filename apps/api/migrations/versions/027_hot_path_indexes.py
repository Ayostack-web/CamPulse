"""Add hot-path indexes.

- materials.uploader_id: SUM(file_size) WHERE uploader_id = ... runs on every
  upload and every GET /user/ai-tokens call (storage allowance computation).
- users.last_active_at: scanned by /digest/social-presence and the 5-minute
  active-count beat job.
- rsvps(user_id), rsvps(lesson_id): FK lookups with CASCADE deletes; no
  indexes existed on either column.

Revision ID: 027
Revises: 026
Create Date: 2026-08-22
"""
from __future__ import annotations

from typing import Union

from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: some environments already carry these indexes from
    # manual application or earlier schema drift.
    op.execute("CREATE INDEX IF NOT EXISTS ix_materials_uploader_id ON materials (uploader_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rsvps_user_id ON rsvps (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rsvps_lesson_id ON rsvps (lesson_id)")


def downgrade() -> None:
    op.drop_index("ix_rsvps_lesson_id", table_name="rsvps")
    op.drop_index("ix_rsvps_user_id", table_name="rsvps")
    op.drop_index("ix_users_last_active_at", table_name="users")
    op.drop_index("ix_materials_uploader_id", table_name="materials")
