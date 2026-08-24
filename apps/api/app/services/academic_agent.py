from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import psycopg
from google import genai
from google.genai import errors, types

from app.core.config import get_settings
from app.core.postgres import get_connection
from app.services.gemini import GeminiError, SERVICE_BUSY_MESSAGE, estimate_cost
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)
settings = get_settings()

FLASH_MODEL = "gemini-flash-lite-latest"
PRO_MODEL = "gemini-pro-latest"

_client: genai.Client | None = None
_vector_store: VectorStore | None = None
_prompt_cache_client: Any | None = None


def _get_prompt_cache_client() -> Any | None:
    """Lazily connect to Redis for the exact-match response cache; ``None`` when unavailable."""
    global _prompt_cache_client
    if _prompt_cache_client is not None:
        return _prompt_cache_client
    try:
        import redis

        client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        _prompt_cache_client = client
    except Exception:
        logger.warning("Redis unavailable; academic agent prompt cache disabled.")
        _prompt_cache_client = None
    return _prompt_cache_client


def _prompt_cache_key(model_id: str, prompt: str) -> str:
    return f"vylix:agent:{model_id}:{hashlib.sha256(prompt.encode()).hexdigest()}"


def _prompt_cache_get(key: str) -> str | None:
    client = _get_prompt_cache_client()
    if not client:
        return None
    try:
        raw = client.get(key)
        return raw.decode() if raw is not None else None
    except Exception:
        return None


def _prompt_cache_set(key: str, value: str) -> None:
    client = _get_prompt_cache_client()
    if not client:
        return
    try:
        client.set(key, value, ex=settings.prompt_cache_ttl_seconds)
    except Exception:
        pass


def _track_model_call(model_id: str) -> None:
    """Best-effort daily per-model call counter in Redis for spend attribution."""
    client = _get_prompt_cache_client()
    if not client:
        return
    try:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        key = f"vylix:metrics:model_calls:{day}:{model_id}"
        pipeline = client.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, 2592000)
        pipeline.execute()
    except Exception:
        pass


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=3,
                    initial_delay=1.0,
                    max_delay=8.0,
                    exp_base=2.0,
                    jitter=True,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )
    return _client


def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(persist_directory=settings.temp_dir / "chromadb")
    return _vector_store


# ── Stage 1: Investigator ────────────────────────────────────────────────


def get_student_weakness_metrics(user_id: str) -> str:
    query = """
        SELECT question_id, topic, category, COUNT(*) AS fail_count
        FROM answers
        WHERE user_id = %s AND is_correct = FALSE
        GROUP BY question_id, topic, category
        ORDER BY fail_count DESC
        LIMIT 30
    """
    try:
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
    except psycopg.Error:
        logger.exception("Weakness metrics query failed for user %s", user_id)
        return ""

    if not rows:
        return "No incorrect answers recorded for this student."

    parts: list[str] = ["Student Weakness Report"]
    for row in rows:
        parts.append(
            f"- Question {row['question_id']} | Topic: {row['topic']} | "
            f"Category: {row['category']} | Failed {row['fail_count']} times"
        )
    return "\n".join(parts)


# ── Stage 2: Researcher ─────────────────────────────────────────────────


def resolve_course_context(
    course_code: str, university_id: str | None = None
) -> tuple[str | None, str | None]:
    """Resolve a course code to (course_id, university_id) for retrieval scoping.

    When ``university_id`` is given, the caller's own institution's row wins
    over shared legacy rows and other institutions' rows are ignored.
    """
    query = """
        SELECT
            c.id AS course_id,
            COALESCE(col.university_id, c.university_id) AS university_id
        FROM courses c
        LEFT JOIN departments d ON d.id = c.department_id
        LEFT JOIN colleges col ON col.id = d.college_id
        WHERE LOWER(c.code) = LOWER(%(code)s)
        ORDER BY CASE
            WHEN %(uni)s::uuid IS NULL THEN 0
            WHEN COALESCE(col.university_id, c.university_id) = %(uni)s::uuid THEN 0
            WHEN COALESCE(col.university_id, c.university_id) IS NULL THEN 1
            ELSE 2
        END
        LIMIT 1
    """
    try:
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, {"code": course_code, "uni": university_id})
            row = cursor.fetchone()
    except psycopg.Error:
        logger.exception("Course resolution failed for %s", course_code)
        return None, None
    if not row:
        return None, None
    effective_university = (
        str(row["university_id"]) if row["university_id"] else None
    )
    if (
        university_id
        and effective_university
        and effective_university != university_id
    ):
        return None, None
    return str(row["course_id"]), effective_university


def search_course_vector_chunks(
    course_code: str,
    query: str,
    course_id: str | None = None,
) -> str:
    try:
        store = _get_vector_store()
        enriched = f"[{course_code}] {query}"
        results = store.query(enriched, top_k=5, course_id=course_id)
    except Exception:
        logger.exception("Vector search failed for course %s", course_code)
        return ""

    if not results:
        return "No relevant course material found."

    parts: list[str] = ["Relevant Course Material"]
    for r in results:
        parts.append(f"[{r.source_name} - chunk {r.chunk_index}] {r.text}")
    return "\n\n".join(parts)


# ── Stage 3: Executive Coach ────────────────────────────────────────────


def run_vylix_academic_agent(
    user_id: str,
    course_code: str,
    user_prompt: str,
    task_tier: str = "standard",
    course_id: str | None = None,
) -> str:
    logger.info(
        "Agent start user=%s course=%s tier=%s",
        user_id,
        course_code,
        task_tier,
    )

    weakness = get_student_weakness_metrics(user_id)

    if course_id is None:
        course_id, _university_id = resolve_course_context(course_code)
    if course_id is None:
        logger.warning(
            "Agent could not resolve course %r; skipping material retrieval",
            course_code,
        )
        material = "No relevant course material found."
    else:
        material = search_course_vector_chunks(
            course_code, user_prompt, course_id=course_id
        )

    tier = "complex" if task_tier == "complex" else "standard"
    if tier == "complex" and not settings.pro_tier_enabled:
        logger.warning(
            "Pro tier disabled by config; downgrading to Flash user=%s course=%s",
            user_id,
            course_code,
        )
        tier = "standard"

    model_id = PRO_MODEL if tier == "complex" else FLASH_MODEL

    system = (
        "You are the Vylix Autonomous Academic Coach - a private tutor. "
        "You have been given the student's historical weakness data and relevant "
        "course material. Synthesize them into a hyper-personalized, actionable response."
    )

    prompt = (
        f"## Weakness Data\n{weakness}\n\n"
        f"## Course Material\n{material}\n\n"
        f"## Student Request\n{user_prompt}"
    )

    cache_key = _prompt_cache_key(model_id, prompt)
    cached = _prompt_cache_get(cache_key)
    if cached is not None:
        logger.info(
            "Agent prompt-cache hit user=%s course=%s tier=%s",
            user_id,
            course_code,
            task_tier,
        )
        from app.services.usage_log import record_ai_usage

        record_ai_usage(
            model=model_id,
            feature="study_agent",
            user_id=user_id,
            task_tier=tier,
            dedup_hit=True,
        )
        return cached

    if tier == "complex":
        logger.warning(
            "agent_pro_call user=%s course=%s prompt_chars=%d",
            user_id,
            course_code,
            len(prompt),
        )
    _track_model_call(model_id)

    client = _get_client()

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )
    except (errors.ClientError, errors.ServerError) as e:
        logger.error("Gemini SDK call failed for user %s course %s: %s", user_id, course_code, e)
        raise GeminiError(SERVICE_BUSY_MESSAGE, status_code=e.code)
    except Exception:
        logger.exception("Gemini call failed for user %s course %s", user_id, course_code)
        raise GeminiError(SERVICE_BUSY_MESSAGE)

    result = response.text

    _prompt_cache_set(cache_key, result)

    try:
        meta = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(meta, "prompt_token_count", 0) or 0
        completion_tokens = getattr(meta, "candidates_token_count", 0) or 0
        cost = estimate_cost(model_id, prompt_tokens, completion_tokens)
        logger.info(
            "gemini_usage model=%s user=%s course=%s prompt_tokens=%d completion_tokens=%d total_tokens=%d cost_usd=%.6f",
            model_id,
            user_id,
            course_code,
            prompt_tokens,
            completion_tokens,
            prompt_tokens + completion_tokens,
            cost,
        )
        from app.services.usage_log import record_ai_usage

        record_ai_usage(
            model=model_id,
            feature="study_agent",
            user_id=user_id,
            task_tier=tier,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            est_cost_usd=cost,
        )
    except Exception:
        logger.warning("Failed to parse Gemini SDK usage metadata", exc_info=True)

    logger.info("Agent complete output_length=%d", len(result))
    return result
