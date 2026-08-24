"""scope material_chunks by course and university

Retrieval previously searched every embedded chunk across ALL institutions:
the agent merely prepended "[COURSE CODE]" to the embedding text, so a UNILAG
student could be served FUNAAB lecture chunks whenever they were semantically
closest. This migration adds institutional scoping:

* ``material_chunks.course_id`` / ``university_id`` -- resolved through
  ``materials -> topics -> courses -> departments -> colleges`` and backfilled
  for every chunk whose ``document_id`` is a material UUID.
* ``match_material_chunks(...)`` grows a nullable ``match_course_id`` filter so
  callers can restrict search to one course's content.

Revision ID: 023
Revises: 022
Create Date: 2026-08-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIMENSIONS = 768

_BACKFILL = """
UPDATE material_chunks mc
SET course_id = c.id,
    university_id = col.university_id
FROM materials m
JOIN topics t ON t.id = m.topic_id
JOIN courses c ON c.id = t.course_id
LEFT JOIN departments d ON d.id = c.department_id
LEFT JOIN colleges col ON col.id = d.college_id
WHERE mc.document_id = m.id::text
"""


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE material_chunks
        ADD COLUMN IF NOT EXISTS course_id UUID REFERENCES courses(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE material_chunks
        ADD COLUMN IF NOT EXISTS university_id UUID REFERENCES universities(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_material_chunks_course_id "
        "ON material_chunks (course_id)"
    )
    op.execute(_BACKFILL)

    op.execute(
        f"DROP FUNCTION IF EXISTS match_material_chunks(VECTOR({DIMENSIONS}), TEXT, INTEGER)"
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION match_material_chunks(
            query_embedding VECTOR({DIMENSIONS}),
            match_document_id TEXT DEFAULT NULL,
            match_count INTEGER DEFAULT 5,
            match_course_id UUID DEFAULT NULL
        )
        RETURNS TABLE (
            id BIGINT,
            document_id TEXT,
            source_name TEXT,
            chunk_index INTEGER,
            content TEXT,
            similarity DOUBLE PRECISION
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                mc.id,
                mc.document_id,
                mc.source_name,
                mc.chunk_index,
                mc.content,
                1 - (mc.embedding <=> query_embedding) AS similarity
            FROM material_chunks mc
            WHERE mc.embedding IS NOT NULL
              AND (match_document_id IS NULL OR mc.document_id = match_document_id)
              AND (match_course_id IS NULL OR mc.course_id = match_course_id)
            ORDER BY mc.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        f"DROP FUNCTION IF EXISTS match_material_chunks(VECTOR({DIMENSIONS}), TEXT, INTEGER, UUID)"
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION match_material_chunks(
            query_embedding VECTOR({DIMENSIONS}),
            match_document_id TEXT DEFAULT NULL,
            match_count INTEGER DEFAULT 5
        )
        RETURNS TABLE (
            id BIGINT,
            document_id TEXT,
            source_name TEXT,
            chunk_index INTEGER,
            content TEXT,
            similarity DOUBLE PRECISION
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                mc.id,
                mc.document_id,
                mc.source_name,
                mc.chunk_index,
                mc.content,
                1 - (mc.embedding <=> query_embedding) AS similarity
            FROM material_chunks mc
            WHERE mc.embedding IS NOT NULL
              AND (match_document_id IS NULL OR mc.document_id = match_document_id)
            ORDER BY mc.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_material_chunks_course_id")
    op.execute("ALTER TABLE material_chunks DROP COLUMN IF EXISTS university_id")
    op.execute("ALTER TABLE material_chunks DROP COLUMN IF EXISTS course_id")
