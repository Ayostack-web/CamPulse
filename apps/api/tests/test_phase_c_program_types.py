"""Phase C: institution program types and program-aware level mapping."""
from __future__ import annotations

import uuid

import pytest

from app.database import async_session
from app.models import University
from app.services.course_scope import level_to_int


def test_university_levels():
    assert level_to_int("300L") == 300
    assert level_to_int("100") == 100
    assert level_to_int("500L", "university") == 500


def test_polytechnic_nd_and_hnd_levels():
    assert level_to_int("ND1", "polytechnic") == 100
    assert level_to_int("ND2", "polytechnic") == 200
    assert level_to_int("HND1", "polytechnic") == 300
    assert level_to_int("HND2", "polytechnic") == 400
    assert level_to_int("hnd2 ft", "polytechnic") == 400


def test_college_of_education_levels():
    assert level_to_int("NCE1", "college_of_education") == 100
    assert level_to_int("NCE3", "college_of_education") == 300


def test_garbage_and_missing_levels_fall_back():
    assert level_to_int(None) == 100
    assert level_to_int("") == 100
    assert level_to_int("weird") == 100
    # small bare numbers still map to year scale for universities
    assert level_to_int("2", "university") == 200


@pytest.mark.asyncio
async def test_program_type_defaults_and_persists(db_schema):
    plain = University(id=str(uuid.uuid4()), code=f"PT{uuid.uuid4().hex[:6]}", name="Plain Uni")
    poly = University(
        id=str(uuid.uuid4()),
        code=f"PT{uuid.uuid4().hex[:6]}",
        name="Tech Poly",
        program_type="polytechnic",
    )
    try:
        async with async_session() as db:
            db.add_all([plain, poly])
            await db.commit()
            fetched_plain = await db.get(University, plain.id)
            fetched_poly = await db.get(University, poly.id)
        assert fetched_plain.program_type == "university"
        assert fetched_poly.program_type == "polytechnic"
    finally:
        async with async_session() as db:
            for uni_id in (plain.id, poly.id):
                obj = await db.get(University, uni_id)
                if obj:
                    await db.delete(obj)
            await db.commit()
