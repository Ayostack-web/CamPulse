"""Solved Question Bank services.

Two-stage pipeline that turns past-question papers into a cached library of
solved questions (the high-margin paid product):

1. ``extract_questions`` pulls individual questions out of an exam paper.
2. ``solve_question`` produces a structured answer (answer/explanation/mistake).

Both run on Gemini Flash-Lite via ``app.services.gemini.call``. Because the
output is stored in the DB and served as content, the marginal cost of serving
an answer to an unlimited number of students is ~₦0.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from typing import Any

from app.core.postgres import get_connection
from app.services import gemini
from app.services.gemini import estimate_cost

logger = logging.getLogger(__name__)

SOLVE_MODEL = "gemini-flash-lite-latest"
MAX_EXTRACT_CHARS = 30000

# OCR glyph variants mapped to their canonical ASCII form before hashing.
_OCR_CHAR_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00d7": "x",
        "\u00f7": "/",
        "\u2026": "...",
    }
)

# Kept in the fingerprint: alphanumerics plus math operators, so "2 + 2"
# never collapses into "22". Decimal points are protected separately below.
_HASH_STRIP_RE = re.compile(r"[^a-z0-9+*/=<>:.-]+")
# Dots are only kept when sandwiched between digits (a decimal point);
# sentence/trailing periods are OCR noise and get stripped.
_DECIMAL_DOT_RE = re.compile(r"\.(?!\d)|(?<!\d)\.")


def question_hash(text: str) -> str:
    """Content fingerprint used for deduplication across papers and schools.

    Normalizes case, whitespace and unicode look-alikes (NFKC), maps common
    OCR punctuation variants (smart quotes, dashes) to their canonical form,
    then strips non-semantic punctuation. Math operators and decimal points
    are preserved so numerically distinct questions never merge.
    """
    normalized = unicodedata.normalize("NFKC", text).translate(_OCR_CHAR_MAP)
    normalized = _DECIMAL_DOT_RE.sub("", normalized.lower())
    normalized = _HASH_STRIP_RE.sub("", normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_json(result: str) -> dict[str, Any] | None:
    cleaned = result.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("\n", 1)[0]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def material_full_text(material_id: str) -> str | None:
    """Concatenate the ingested chunks for a past-question document."""
    query = """
        SELECT content FROM material_chunks
        WHERE document_id = %s
        ORDER BY chunk_index ASC
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (material_id,))
        rows = cursor.fetchall()
    if not rows:
        return None
    return "\n\n".join(str(row["content"]) for row in rows)


def extract_questions(text: str, user_id: str | None = None) -> list[dict[str, Any]]:
    """Stage 1: pull individual exam questions out of a past-question paper."""
    system = (
        "You are parsing a university past-question exam paper into individual questions. "
        'Respond with ONLY JSON: {"questions": [{"text": "the question as written", "year": 2023}]}. '
        "Preserve each question verbatim. Skip headers, page numbers and instructions. "
        "If a question is unclear, include it as written. No markdown, no code fences."
    )
    prompt = f"Exam paper:\n{text[:MAX_EXTRACT_CHARS]}\n\nExtract every exam question as JSON."
    result = gemini.call(prompt, system_instruction=system, user_id=user_id, feature="solved_bank_extract")
    if not result:
        return []
    parsed = _parse_json(result)
    if not parsed:
        logger.warning("Question extraction returned unparsable JSON: %s", result[:300])
        return []
    questions = parsed.get("questions")
    if not isinstance(questions, list):
        return []
    return [q for q in questions if isinstance(q, dict) and str(q.get("text") or "").strip()]


def solve_question(
    course_code: str,
    question: str,
    user_id: str | None = None,
) -> tuple[dict[str, Any], float]:
    """Stage 2: solve one question, returning (answer dict, usd cost)."""
    system = (
        f"You are an expert university tutor for the course {course_code}. "
        "Solve the past exam question below. Respond with ONLY JSON with three keys: "
        '"answer" (the correct answer), "explanation" (step-by-step reasoning in plain English), '
        '"mistake" (the most common student mistake and how to avoid it). '
        "No markdown, no code fences."
    )
    prompt = f"Question: {question}\n\nSolve it."
    usage: list[tuple[int, int]] = []
    result = gemini.call(
        prompt, system_instruction=system, user_id=user_id, usage=usage,
        feature="solved_bank_solve",
    )
    if not result:
        return {"answer": "", "explanation": "", "mistake": ""}, 0.0

    parsed = _parse_json(result)
    if parsed is None:
        parsed = {"answer": result, "explanation": "", "mistake": ""}

    cost = 0.0
    if usage:
        prompt_tokens, completion_tokens = usage[0]
        cost = estimate_cost(SOLVE_MODEL, prompt_tokens, completion_tokens)
    return parsed, cost
