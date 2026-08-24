"""per-institution course codes

``courses.code`` was globally unique, so two universities could never both have
"CSC 201" -- the catalog implicitly assumed a single institution and every
downstream lookup (materials, solved bank, agent retrieval) inherited that.

This migration:

* adds ``courses.university_id`` (set for general/no-department courses; the
  university of department-backed courses is derived through
  ``departments -> colleges``),
* backfills it from that chain where derivable,
* drops the global unique on ``code`` in favour of two partial unique indexes:
  ``(department_id, code)`` for department courses and
  ``(university_id, code)`` for general courses.

Rows whose university cannot be derived keep ``university_id IS NULL`` and act
as shared legacy content visible to every institution.

Revision ID: 024
Revises: 023
Create Date: 2026-08-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BACKFILL = """
UPDATE courses c
SET university_id = col.university_id
FROM departments d
JOIN colleges col ON col.id = d.college_id
WHERE c.department_id = d.id AND c.university_id IS NULL
"""

_DROP_GLOBAL_UNIQUE = """
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    SELECT con.conname INTO constraint_name
    FROM pg_constraint con
    JOIN pg_attribute att
      ON att.attrelid = con.conrelid
     AND att.attnum = ANY (con.conkey)
    WHERE con.conrelid = 'courses'::regclass
      AND con.contype = 'u'
      AND array_length(con.conkey, 1) = 1
      AND att.attname = 'code';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE courses DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;
"""

# Some environments created the global uniqueness as a standalone UNIQUE INDEX
# rather than a table constraint; drop those too (except the new partials).
_DROP_UNIQUE_INDEXES = """
DO $$
DECLARE
    index_name TEXT;
BEGIN
    FOR index_name IN
        SELECT i.relname
        FROM pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE t.relname = 'courses'
          AND n.nspname = current_schema()
          AND ix.indisunique
          AND array_length(ix.indkey::int2[], 1) = 1
          AND (
              SELECT att.attname
              FROM pg_attribute att
              WHERE att.attrelid = t.oid
                AND att.attnum = (ix.indkey)[0]
          ) = 'code'
          AND i.relname NOT IN
              ('uq_courses_department_code', 'uq_courses_university_code')
    LOOP
        EXECUTE format('DROP INDEX %I', index_name);
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE courses
        ADD COLUMN IF NOT EXISTS university_id UUID REFERENCES universities(id)
        ON DELETE CASCADE
        """
    )
    op.execute(_BACKFILL)
    op.execute(_DROP_GLOBAL_UNIQUE)
    op.execute(_DROP_UNIQUE_INDEXES)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_courses_department_code "
        "ON courses (department_id, code) WHERE department_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_courses_university_code "
        "ON courses (university_id, code) "
        "WHERE department_id IS NULL AND university_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_courses_university_id ON courses (university_id)"
    )


def downgrade() -> None:
    # Re-adding a single-column unique on code requires that no duplicate codes
    # exist across institutions; if per-school rows were created since upgrade,
    # deduplicate manually before downgrading.
    op.execute("DROP INDEX IF EXISTS ix_courses_university_id")
    op.execute("DROP INDEX IF EXISTS uq_courses_university_code")
    op.execute("DROP INDEX IF EXISTS uq_courses_department_code")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_courses_code_legacy ON courses (code)"
    )
    op.execute("ALTER TABLE courses DROP COLUMN IF EXISTS university_id")
