"""Per-institution course resolution tests (real DB via db_schema fixture)."""
from __future__ import annotations

import uuid

import pytest

from app.database import async_session
from app.models import College, Course, Department, University
from app.services.academic_agent import resolve_course_context
from app.services.course_scope import course_exists_anywhere, find_course


def _suffix() -> str:
    return uuid.uuid4().hex[:8].upper()


@pytest.mark.asyncio
async def test_find_course_resolves_within_institution(db_schema):
    sfx = _suffix()
    uni_a = University(id=str(uuid.uuid4()), code=f"UA{sfx}", name="Uni A")
    uni_b = University(id=str(uuid.uuid4()), code=f"UB{sfx}", name="Uni B")
    college = College(id=str(uuid.uuid4()), name="Sci", code=f"C{sfx}", university_id=uni_a.id)
    dept = Department(id=str(uuid.uuid4()), name="CS", code=f"D{sfx}", college_id=college.id)
    code = f"TST {sfx}"
    course_dept = Course(
        id=str(uuid.uuid4()), code=code, title="Dept course",
        level=200, department_id=dept.id,
    )
    course_other_school = Course(
        id=str(uuid.uuid4()), code=code, title="Other school general",
        level=100, is_general=True, university_id=uni_b.id,
    )
    try:
        async with async_session() as db:
            db.add_all([uni_a, uni_b])
            await db.flush()
            db.add_all([college, dept, course_dept, course_other_school])
            await db.commit()

            resolved = await find_course(db, code.lower(), uni_a.id)
            assert resolved is not None
            found_course, effective_uni = resolved
            assert found_course.id == course_dept.id
            assert effective_uni == uni_a.id

            resolved_b = await find_course(db, code, uni_b.id)
            assert resolved_b is not None
            assert resolved_b[0].id == course_other_school.id
            assert resolved_b[1] == uni_b.id
    finally:
        async with async_session() as db:
            for cid in (course_dept.id, course_other_school.id):
                obj = await db.get(Course, cid)
                if obj:
                    await db.delete(obj)
            for oid in (dept.id, college.id):
                obj = await db.get(Department if oid == dept.id else College, oid)
                if obj:
                    await db.delete(obj)
            for uid in (uni_a.id, uni_b.id):
                obj = await db.get(University, uid)
                if obj:
                    await db.delete(obj)
            await db.commit()


@pytest.mark.asyncio
async def test_find_course_never_returns_other_institution_row(db_schema):
    sfx = _suffix()
    uni_a = University(id=str(uuid.uuid4()), code=f"UA{sfx}", name="Uni A")
    course_b = Course(
        id=str(uuid.uuid4()), code=f"FOR {sfx}", title="Foreign",
        level=100, is_general=True, university_id=None,
    )
    # give it an owning university different from the viewer's
    uni_b = University(id=str(uuid.uuid4()), code=f"UB{sfx}", name="Uni B")
    course_b.university_id = uni_b.id
    try:
        async with async_session() as db:
            db.add_all([uni_a, uni_b])
            await db.flush()
            db.add(course_b)
            await db.commit()

            assert await find_course(db, f"for {sfx}", uni_a.id) is None
            assert await find_course(db, f"FOR {sfx}", None) is not None
    finally:
        async with async_session() as db:
            obj = await db.get(Course, course_b.id)
            if obj:
                await db.delete(obj)
            for uid in (uni_a.id, uni_b.id):
                obj = await db.get(University, uid)
                if obj:
                    await db.delete(obj)
            await db.commit()


@pytest.mark.asyncio
async def test_legacy_null_university_courses_stay_visible(db_schema):
    sfx = _suffix()
    uni_a = University(id=str(uuid.uuid4()), code=f"UA{sfx}", name="Uni A")
    legacy = Course(
        id=str(uuid.uuid4()), code=f"OLD {sfx}", title="Legacy",
        level=100, is_general=True, university_id=None,
    )
    try:
        async with async_session() as db:
            db.add(uni_a)
            await db.flush()
            db.add(legacy)
            await db.commit()

            resolved = await find_course(db, f"old {sfx}", uni_a.id)
            assert resolved is not None
            assert resolved[0].id == legacy.id
            assert resolved[1] is None
    finally:
        async with async_session() as db:
            obj = await db.get(Course, legacy.id)
            if obj:
                await db.delete(obj)
            obj = await db.get(University, uni_a.id)
            if obj:
                await db.delete(obj)
            await db.commit()


@pytest.mark.asyncio
async def test_sync_resolver_prefers_callers_university(db_schema):
    sfx = _suffix()
    uni_a = University(id=str(uuid.uuid4()), code=f"UA{sfx}", name="Uni A")
    uni_b = University(id=str(uuid.uuid4()), code=f"UB{sfx}", name="Uni B")
    code = f"SYN {sfx}"
    course_a = Course(
        id=str(uuid.uuid4()), code=code, title="A copy",
        level=100, is_general=True, university_id=uni_a.id,
    )
    course_b = Course(
        id=str(uuid.uuid4()), code=code, title="B copy",
        level=100, is_general=True, university_id=uni_b.id,
    )
    try:
        async with async_session() as db:
            db.add_all([uni_a, uni_b])
            await db.flush()
            db.add_all([course_a, course_b])
            await db.commit()

        got_id, got_uni = resolve_course_context(code, uni_a.id)
        assert (got_id, got_uni) == (course_a.id, uni_a.id)

        got_id, got_uni = resolve_course_context(code, uni_b.id)
        assert (got_id, got_uni) == (course_b.id, uni_b.id)

        assert resolve_course_context(f"NOSUCH {sfx}", uni_a.id) == (None, None)

        async with async_session() as db:
            exists = await course_exists_anywhere(db, code)
            assert exists is not None
            assert exists[0] in {course_a.id, course_b.id}
    finally:
        async with async_session() as db:
            for cid in (course_a.id, course_b.id):
                obj = await db.get(Course, cid)
                if obj:
                    await db.delete(obj)
            for uid in (uni_a.id, uni_b.id):
                obj = await db.get(University, uid)
                if obj:
                    await db.delete(obj)
            await db.commit()
