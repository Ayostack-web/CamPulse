from __future__ import annotations

import hashlib
import logging
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


def search_course_vector_chunks(course_code: str, query: str) -> str:
    try:
        store = _get_vector_store()
        enriched = f"[{course_code}] {query}"
        results = store.query(enriched, top_k=5)
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
) -> str:
    logger.info(
        "Agent start user=%s course=%s tier=%s",
        user_id,
        course_code,
        task_tier,
    )

    weakness = get_student_weakness_metrics(user_id)
    material = search_course_vector_chunks(course_code, user_prompt)

    model_id = PRO_MODEL if task_tier == "complex" else FLASH_MODEL

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
        return cached

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
    except Exception:
        logger.warning("Failed to parse Gemini SDK usage metadata", exc_info=True)

    logger.info("Agent complete output_length=%d", len(result))
    return result
