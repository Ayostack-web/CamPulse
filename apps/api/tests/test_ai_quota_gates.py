"""Regression tests for the AI cost-leak fixes:

1. Document chat endpoints must require authentication (they used to serve
   Gemini answers anonymously with no quota spend).
2. The client-supplied ``task_tier="complex"`` (Pro model) must be reserved
   for users holding an active paid pass.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.routers.study_agent as study_agent_module
from app.database import get_db
from app.deps import CurrentUser, check_ai_token_quota
from app.main import app


def _fake_user() -> CurrentUser:
    # ``user`` only needs whatever downstream code touches once the course
    # resolver is stubbed out — nothing here opens the database.
    return CurrentUser(
        id="route-test-user",
        email=None,
        full_name=None,
        user=SimpleNamespace(university_id=None),
    )


@pytest.fixture
def override_auth():
    def _install(user: CurrentUser) -> None:
        async def _fake_db():
            yield None

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[check_ai_token_quota] = lambda: user

    try:
        yield _install
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(check_ai_token_quota, None)


async def test_general_chat_requires_auth(client):
    resp = await client.post(
        "/api/v1/documents/general-chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


async def test_document_chat_requires_auth(client):
    resp = await client.post(
        "/api/v1/documents/chat",
        json={"document_id": "doc-1", "query": "hi"},
    )
    assert resp.status_code == 401


def _patch_agent(monkeypatch, has_paid_pass: bool, seen: dict) -> None:
    async def fake_scope(db, university_id, course_code):
        return "course-1", None

    async def fake_has_pass(db, user_id):
        return has_paid_pass

    def fake_run(**kwargs):
        seen.update(kwargs)
        return "plan"

    monkeypatch.setattr(study_agent_module, "_resolve_scoped_course", fake_scope)
    monkeypatch.setattr(study_agent_module, "has_active_paid_pass", fake_has_pass)
    monkeypatch.setattr(study_agent_module, "run_vylix_academic_agent", fake_run)


async def test_complex_tier_downgraded_without_paid_pass(client, override_auth, monkeypatch):
    override_auth(_fake_user())
    seen: dict = {}
    _patch_agent(monkeypatch, has_paid_pass=False, seen=seen)

    resp = await client.post(
        "/api/v1/study-agent/run",
        json={"course_code": "CSC101", "prompt": "study plan", "task_tier": "complex"},
    )

    assert resp.status_code == 200
    assert seen["task_tier"] == "standard"
    assert resp.json()["tier"] == "standard"


async def test_complex_tier_kept_with_paid_pass(client, override_auth, monkeypatch):
    override_auth(_fake_user())
    seen: dict = {}
    _patch_agent(monkeypatch, has_paid_pass=True, seen=seen)

    resp = await client.post(
        "/api/v1/study-agent/run",
        json={"course_code": "CSC101", "prompt": "study plan", "task_tier": "complex"},
    )

    assert resp.status_code == 200
    assert seen["task_tier"] == "complex"
    assert resp.json()["tier"] == "complex"
