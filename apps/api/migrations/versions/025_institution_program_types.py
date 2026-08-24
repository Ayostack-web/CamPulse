"""institution program types (university / polytechnic / college of education)

Polytechnic and college-of-education students use year labels like "ND1",
"HND2" and "NCE3". Nothing in the schema distinguished institution kinds, so
level normalization and onboarding copy assumed universities everywhere.

Adds ``universities.program_type`` (default ``'university'``, so every existing
row keeps its meaning).

Revision ID: 025
Revises: 024
Create Date: 2026-08-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE universities
        ADD COLUMN IF NOT EXISTS program_type TEXT NOT NULL DEFAULT 'university'
        """
    )
    op.execute(
        """
        ALTER TABLE universities DROP CONSTRAINT IF EXISTS ck_universities_program_type
        """
    )
    op.execute(
        """
        ALTER TABLE universities ADD CONSTRAINT ck_universities_program_type
        CHECK (program_type IN ('university', 'polytechnic', 'college_of_education'))
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE universities DROP CONSTRAINT IF EXISTS ck_universities_program_type"
    )
    op.execute("ALTER TABLE universities DROP COLUMN IF EXISTS program_type")
