"""add content_hash to materials

Revision ID: 021
Revises: 020
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op


revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: the drive import task may have already created the column
    # at runtime via ALTER TABLE ... ADD COLUMN IF NOT EXISTS.
    op.execute("ALTER TABLE materials ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_materials_content_hash ON materials (content_hash)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_materials_content_hash")
    op.execute("ALTER TABLE materials DROP COLUMN IF EXISTS content_hash")
