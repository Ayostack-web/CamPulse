"""Add last_opened_at to materials for recently-opened ordering in /recent.

Revision ID: 029
Revises: 028
Create Date: 2026-08-24
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_materials_last_opened_at", "materials", ["last_opened_at"])


def downgrade() -> None:
    op.drop_index("ix_materials_last_opened_at", table_name="materials")
    op.drop_column("materials", "last_opened_at")
