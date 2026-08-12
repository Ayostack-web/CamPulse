"""Solved Question Bank background jobs.

Pipeline: a ``generate_for_course`` task extracts questions from every
past-question paper of a course (deduped by content hash), then fans the
individual solves out to a ``solve_question`` group and finalizes the batch
with a chord callback. A weekly ``refill_all`` keeps every course topped up.
"""
from __future__ import annotations

import json
import logging
from uuid import uuid4

from celery import chord, group

from app.core.celery_app import celery_app
from app.core.postgres import get_connection
from app.services.solved_bank import (
    extract_questions,
    material_full_text,
    question_hash,
    solve_question,
)

logger = logging.getLogger(__name__)

DEFAULT_TARGET = 300


# ── DB helpers ──────────────────────────────────────────────────────


def _insert_batch(batch_id: str, course_id: str, trigger: str, target_count: int) -> None:
    query = """
        INSERT INTO solved_bank_batches
            (id, course_id, trigger, target_count, queued_count, completed_count,
             failed_count, cost_usd_total, status, started_at, created_at)
        VALUES (%s, %s, %s, %s, 0, 0, 0, 0.0, 'RUNNING', NOW(), NOW())
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (batch_id, course_id, trigger, target_count))
        conn.commit()


def _past_question_materials(course_id: str) -> list[dict]:
    query = """
        SELECT m.id, m.exam_year, m.semester
        FROM materials m JOIN topics t ON t.id = m.topic_id
        WHERE t.course_id = %s AND m.is_past_question = TRUE
        ORDER BY m.uploaded_at ASC
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (course_id,))
        return cursor.fetchall()


def _insert_question(
    batch_id: str,
    course_id: str,
    material_id: str,
    question_text: str,
    year: int | None,
    semester: str | None,
) -> str | None:
    """Insert a QUEUED question, deduped by content hash. Returns id or None."""
    query = """
        INSERT INTO solved_questions
            (id, batch_id, course_id, material_id, question_hash, question_text,
             year, semester, status, model, cost_usd, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'QUEUED', 'gemini-flash-lite-latest', 0.0, NOW(), NOW())
        ON CONFLICT (question_hash) DO NOTHING
        RETURNING id
    """
    qid = str(uuid4())
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            query,
            (qid, batch_id, course_id, material_id, question_hash(question_text), question_text, year, semester),
        )
        row = cursor.fetchone()
        conn.commit()
    return str(row["id"]) if row else None


def _set_queued_count(batch_id: str, queued: int) -> None:
    query = "UPDATE solved_bank_batches SET queued_count = %s WHERE id = %s"
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (queued, batch_id))
        conn.commit()


def _mark_solved(question_id: str, answer_json: str, cost_usd: float) -> None:
    query = """
        UPDATE solved_questions
        SET status = 'COMPLETED', answer_text = %s, cost_usd = %s, error = NULL,
            generated_at = NOW(), updated_at = NOW()
        WHERE id = %s
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (answer_json, cost_usd, question_id))
        conn.commit()
    _increment_batch(question_id, cost_usd)


def _mark_failed(question_id: str, error: str) -> None:
    query = """
        UPDATE solved_questions
        SET status = 'FAILED', error = %s, updated_at = NOW()
        WHERE id = %s
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (error[:500], question_id))
        conn.commit()
    _increment_batch(question_id, None)


def _increment_batch(question_id: str, cost_usd: float | None) -> None:
    """Accumulate counters/cost on the batch that owns this question."""
    query = """
        UPDATE solved_bank_batches b
        SET completed_count = completed_count + %(done)s,
            failed_count = failed_count + %(failed)s,
            cost_usd_total = cost_usd_total + COALESCE(%(cost)s, 0.0)
        FROM solved_questions q
        WHERE q.id = %(qid)s AND b.id = q.batch_id
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            query,
            {
                "qid": question_id,
                "done": 1 if cost_usd is not None else 0,
                "failed": 1 if cost_usd is None else 0,
                "cost": cost_usd,
            },
        )
        conn.commit()


def _finalize_batch(batch_id: str) -> None:
    query = """
        UPDATE solved_bank_batches
        SET status = 'COMPLETED', completed_at = NOW()
        WHERE id = %s
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (batch_id,))
        conn.commit()


def _get_queued_question(question_id: str) -> dict | None:
    query = """
        SELECT q.id, q.question_text, c.code AS course_code
        FROM solved_questions q JOIN courses c ON c.id = q.course_id
        WHERE q.id = %s AND q.status = 'QUEUED'
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (question_id,))
        return cursor.fetchone()


# ── Tasks ────────────────────────────────────────────────────────────


@celery_app.task(name="solvedbank.generate_for_course", bind=True, max_retries=1, default_retry_delay=60)
def generate_for_course(
    self,
    course_id: str,
    target_count: int = DEFAULT_TARGET,
    trigger: str = "manual",
) -> dict:
    """Stage 1 extraction + fan-out: build (or top up) a course's solved bank."""
    batch_id = str(uuid4())
    _insert_batch(batch_id, course_id, trigger, target_count)

    question_ids: list[str] = []
    for material in _past_question_materials(course_id):
        text = material_full_text(str(material["id"]))
        if not text:
            continue
        try:
            extracted = extract_questions(text)
        except Exception:
            logger.exception("Question extraction failed for material %s", material["id"])
            continue
        for q in extracted:
            qtext = str(q.get("text") or "").strip()
            if not qtext:
                continue
            qid = _insert_question(
                batch_id,
                course_id,
                str(material["id"]),
                qtext,
                material.get("exam_year"),
                material.get("semester"),
            )
            if qid:
                question_ids.append(qid)
                if len(question_ids) >= target_count:
                    break
        if len(question_ids) >= target_count:
            break

    if not question_ids:
        _finalize_batch(batch_id)
        return {"batch_id": batch_id, "enqueued": 0}

    _set_queued_count(batch_id, len(question_ids))
    work = group(solve_question_task.s(qid) for qid in question_ids)
    chord(work)(finalize_batch.s(batch_id))
    logger.info("Solved bank batch %s enqueued %d solves", batch_id, len(question_ids))
    return {"batch_id": batch_id, "enqueued": len(question_ids)}


@celery_app.task(name="solvedbank.solve_question", bind=True, max_retries=2, default_retry_delay=30)
def solve_question_task(self, question_id: str) -> dict:
    """Stage 2: solve one question and store the cached answer + cost."""
    row = _get_queued_question(question_id)
    if not row:
        return {"question_id": question_id, "status": "missing"}

    try:
        answer, cost = solve_question(str(row["course_code"]), str(row["question_text"]))
        _mark_solved(question_id, json.dumps(answer, ensure_ascii=False), cost)
        return {"question_id": question_id, "status": "completed", "cost_usd": cost}
    except Exception as exc:
        logger.exception("Solve failed for question %s", question_id)
        _mark_failed(question_id, str(exc))
        return {"question_id": question_id, "status": "failed"}


@celery_app.task(name="solvedbank.finalize_batch")
def finalize_batch(results: list | None, batch_id: str) -> None:
    """Chord callback: mark the batch done once all solves finish."""
    _finalize_batch(batch_id)


@celery_app.task(name="solvedbank.refill_all")
def refill_all(target_count: int = DEFAULT_TARGET) -> dict:
    """Weekly top-up: trigger generation for courses below the target."""
    query = """
        SELECT c.id FROM courses c
        WHERE (SELECT COUNT(*) FROM solved_questions q
               WHERE q.course_id = c.id AND q.status = 'COMPLETED' AND q.is_active = TRUE) < %s
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (target_count,))
        rows = cursor.fetchall()

    for row in rows:
        generate_for_course.delay(str(row["id"]), target_count, "schedule")
    logger.info("Solved bank refill triggered for %d courses", len(rows))
    return {"courses_triggered": len(rows)}
