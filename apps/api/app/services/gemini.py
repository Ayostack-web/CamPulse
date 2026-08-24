from __future__ import annotations

import json
import logging
import random
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings

logger = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest"

#: Model used by the urllib-backed call path below.
MODEL_NAME = "gemini-flash-lite-latest"

#: Approximate USD cost per 1M tokens by model (input, output). These are
#: estimates used ONLY for usage/cost logging — verify them against the
#: provider billing dashboard and update as pricing changes. Current as of
#: Aug 2026 (Gemini 3.x production tier; 2.0/2.5 flash are deprecated).
MODEL_PRICES: dict[str, dict[str, float]] = {
    "gemini-flash-lite-latest": {"input": 0.15, "output": 0.60},
    "gemini-3.6-flash": {"input": 1.50, "output": 7.50},
    "gemini-3-flash": {"input": 0.50, "output": 3.00},
    "gemini-pro-latest": {"input": 2.00, "output": 12.00},
}
DEFAULT_PRICE: dict[str, float] = {"input": 0.15, "output": 0.60}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimated USD cost for a single call, for logging only."""
    prices = MODEL_PRICES.get(model, DEFAULT_PRICE)
    return (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1_000_000

MAX_ATTEMPTS = 3
BASE_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 8.0

#: Status codes indicating a transient upstream failure worth retrying.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

#: Friendly message shown when the upstream AI provider is throttled or down.
SERVICE_BUSY_MESSAGE = (
    "The AI service is busy right now. Please wait a moment and try again."
)

#: Friendly message shown when the Gemini API key has exhausted its quota.
QUOTA_EXCEEDED_MESSAGE = (
    "Your AI quota is exhausted. Check your Gemini API plan and billing, or try again later."
)


class GeminiError(Exception):
    """Raised when the Gemini API cannot be reached or returns an error."""

    def __init__(self, detail: str, status_code: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _parse_retry_after(headers: Any, default: float) -> float:
    """Parse the Retry-After header, falling back to ``default`` seconds."""
    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _retry_delay(attempt: int, headers: Any) -> float:
    """Exponential backoff with jitter, honoring Retry-After when present."""
    if attempt == 0:
        return 0.0
    base = min(BASE_RETRY_DELAY * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
    jittered = base * random.uniform(0.5, 1.5)
    return min(_parse_retry_after(headers, jittered), MAX_RETRY_DELAY)


def error_response(exc: GeminiError) -> tuple[int, str]:
    """Map a GeminiError to an (HTTP status, detail) pair for callers."""
    if exc.status_code == 429:
        return 429, QUOTA_EXCEEDED_MESSAGE
    if exc.status_code is None or exc.status_code in RETRYABLE_STATUS:
        return 503, exc.detail or SERVICE_BUSY_MESSAGE
    return 502, exc.detail


def _call(
    prompt: str,
    system_instruction: str | None = None,
    user_id: str | None = None,
    usage: list | None = None,
    feature: str = "unattributed",
) -> str | None:
    """Call Gemini Flash-Lite and return the generated text.

    When ``usage`` is provided (a list), it receives a
    ``(prompt_tokens, completion_tokens)`` tuple so callers can track cost.
    ``feature`` labels the calling surface in the ai_usage table.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY is not configured")

    url = f"{API_BASE}:generateContent?key={settings.gemini_api_key}"

    body: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    data = json.dumps(body).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"})

    for attempt in range(MAX_ATTEMPTS):
        try:
            with urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            break
        except HTTPError as e:
            error_body = e.read().decode(errors="replace")[:500]
            logger.error("Gemini API returned HTTP %s (%s): %s", e.code, e.reason, error_body)
            if e.code in (400, 401, 403):
                raise GeminiError(
                    "Gemini API rejected the request. Check that the API key is valid and has access to the gemini-flash-lite-latest model.",
                    status_code=e.code,
                )
            if e.code not in RETRYABLE_STATUS:
                raise GeminiError(f"Gemini API returned HTTP {e.code} ({e.reason})", status_code=e.code)
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(_retry_delay(attempt, e.headers))
            else:
                detail = QUOTA_EXCEEDED_MESSAGE if e.code == 429 else SERVICE_BUSY_MESSAGE
                raise GeminiError(detail, status_code=e.code)
        except (URLError, TimeoutError) as e:
            logger.error("Gemini API call failed: %s", e)
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(_retry_delay(attempt, {}))
            else:
                raise GeminiError(SERVICE_BUSY_MESSAGE, status_code=503)
        except json.JSONDecodeError as e:
            logger.error("Gemini API returned invalid JSON: %s", e)
            raise GeminiError("Gemini API returned an invalid response")

    try:
        meta = result.get("usageMetadata") or {}
        prompt_tokens = meta.get("promptTokenCount") or 0
        completion_tokens = meta.get("candidatesTokenCount") or 0
        total_tokens = meta.get("totalTokenCount") or (prompt_tokens + completion_tokens)
        if usage is not None:
            usage.append((prompt_tokens, completion_tokens))
        cost = estimate_cost(MODEL_NAME, prompt_tokens, completion_tokens)
        logger.info(
            "gemini_usage model=%s user=%s feature=%s prompt_tokens=%d completion_tokens=%d total_tokens=%d cost_usd=%.6f",
            MODEL_NAME,
            user_id or "-",
            feature,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost,
        )
        from app.services.usage_log import record_ai_usage

        record_ai_usage(
            model=MODEL_NAME,
            feature=feature,
            user_id=user_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            est_cost_usd=cost,
        )
    except Exception:
        logger.warning("Failed to parse Gemini usage metadata", exc_info=True)

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        logger.warning("Gemini response contained no text: %s", json.dumps(result)[:500])
        raise GeminiError("Gemini API returned an empty response")


def generate_insights(
    text: str,
    department_code: str,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    system = (
        "You are a study assistant for university students. "
        "Analyze the given academic material and return JSON with exactly three keys:\n"
        '- "summary": a 2-3 sentence summary of the key content\n'
        '- "questions": an array of 3-5 meaningful study questions based on the material\n'
        '- "tips": an array of 2-3 practical study tips specific to this material\n'
        "Respond with ONLY the JSON object, no markdown, no code fences."
    )
    prompt = (
        f"Department: {department_code}\n\n"
        f"Material content:\n{text[:6000]}\n\n"
        "Generate summary, questions, and tips as JSON."
    )

    try:
        result = _call(prompt, system_instruction=system, user_id=user_id, feature="insights")
    except GeminiError as exc:
        logger.error("Insights generation failed: %s", exc)
        return None
    if not result:
        return None

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


def chat(query: str, context: str, user_id: str | None = None, feature: str = "document_chat") -> str | None:
    system = (
        "You are a study assistant helping a university student understand their course material. "
        "Answer the student's question based ONLY on the provided document context. "
        "If the context doesn't contain enough information, say so clearly. "
        "Be concise and educational."
    )
    prompt = (
        f"Document context:\n{context[:5000]}\n\n"
        f"Student question: {query}\n\n"
        "Answer:"
    )
    return _call(prompt, system_instruction=system, user_id=user_id, feature=feature)


def general_chat(conversation: str, user_id: str | None = None) -> str | None:
    system = (
        "You are a helpful AI study assistant for university students. "
        "Answer the student's questions clearly and educationally. "
        "Be concise but thorough. If the question is about a specific course topic, "
        "provide explanations, examples, and study tips where relevant. "
        "You can help with any academic question — math, science, humanities, study strategies, etc."
    )
    prompt = f"Conversation:\n{conversation}\n\nAssistant:"
    return _call(prompt, system_instruction=system, user_id=user_id, feature="general_chat")


def call(
    prompt: str,
    system_instruction: str | None = None,
    user_id: str | None = None,
    usage: list | None = None,
    feature: str = "unattributed",
) -> str | None:
    """Public wrapper around the Flash-Lite call for feature services.

    ``usage`` is an optional list that receives a ``(prompt_tokens,
    completion_tokens)`` tuple so callers can track per-call cost.
    ``feature`` labels the calling surface in the ai_usage table.
    """
    return _call(
        prompt,
        system_instruction=system_instruction,
        user_id=user_id,
        usage=usage,
        feature=feature,
    )
