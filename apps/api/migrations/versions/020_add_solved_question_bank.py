"""add solved question bank tables

Revision ID: 020
Revises: 019
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(bind, table: str, index: str) -> bool:
    return any(ix["name"] == index for ix in inspect(bind).get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()

    if not inspect(bind).has_table("solved_bank_batches"):
        op.create_table(
            "solved_bank_batches",
            sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("course_id", sa.UUID(as_uuid=False), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("trigger", sa.String(), nullable=False, server_default="manual"),
            sa.Column("target_count", sa.Integer(), nullable=False, server_default="300"),
            sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_usd_total", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("status", sa.String(), nullable=False, server_default="RUNNING"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not _index_exists(bind, "solved_bank_batches", "ix_solved_bank_batches_course_id"):
        op.create_index("ix_solved_bank_batches_course_id", "solved_bank_batches", ["course_id"])
    if not _index_exists(bind, "solved_bank_batches", "ix_solved_bank_batches_status"):
        op.create_index("ix_solved_bank_batches_status", "solved_bank_batches", ["status"])

    if not inspect(bind).has_table("solved_questions"):
        op.create_table(
            "solved_questions",
            sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("batch_id", sa.UUID(as_uuid=False), sa.ForeignKey("solved_bank_batches.id", ondelete="SET NULL"), nullable=True),
            sa.Column("course_id", sa.UUID(as_uuid=False), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("material_id", sa.UUID(as_uuid=False), sa.ForeignKey("materials.id", ondelete="SET NULL"), nullable=True),
            sa.Column("question_hash", sa.String(64), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("answer_text", sa.Text(), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("semester", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=False, server_default="gemini-2.0-flash"),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column(
                "status",
                sa.Enum("QUEUED", "COMPLETED", "FAILED", name="SolvedQuestionStatus", native_enum=False, create_constraint=True),
                nullable=False,
                server_default="QUEUED",
            ),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("question_hash", name="uq_solved_questions_hash"),
        )
    if not _index_exists(bind, "solved_questions", "ix_solved_questions_course_id"):
        op.create_index("ix_solved_questions_course_id", "solved_questions", ["course_id"])
    if not _index_exists(bind, "solved_questions", "ix_solved_questions_course_id_status"):
        op.create_index("ix_solved_questions_course_id_status", "solved_questions", ["course_id", "status"])
    if not _index_exists(bind, "solved_questions", "ix_solved_questions_course_id_is_sample"):
        op.create_index("ix_solved_questions_course_id_is_sample", "solved_questions", ["course_id", "is_sample"])


def downgrade() -> None:
    op.drop_index("ix_solved_questions_course_id_is_sample", table_name="solved_questions")
    op.drop_index("ix_solved_questions_course_id_status", table_name="solved_questions")
    op.drop_index("ix_solved_questions_course_id", table_name="solved_questions")
    op.drop_table("solved_questions")
    op.drop_index("ix_solved_bank_batches_status", table_name="solved_bank_batches")
    op.drop_index("ix_solved_bank_batches_course_id", table_name="solved_bank_batches")
    op.drop_table("solved_bank_batches")
