"""University-scoped course resolution.

A course's *effective* university is its explicit ``university_id`` (general /
no-department courses) or the one derived through ``department -> college``.
Courses whose university cannot be derived are shared legacy content visible
to every institution.
"""
from __future__ import annotations

import re

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import College, Course, Department

_EFFECTIVE_UNIVERSITY = func.coalesce(College.university_id, Course.university_id)


def level_to_int(current_level: str | None, program_type: str | None = None) -> int:
    """Normalize a student's level label onto the 100-based course scale.

    Universities write "100L"/"300"; polytechnics write "ND1"/"HND2"
    (HND years continue after ND, i.e. HND1 ~ 300 level); colleges of
    education write "NCE1".."NCE3". Unparseable input falls back to 100-level.
    """
    text = (current_level or "").upper()
    match = re.search(r"\d+", text)
    if not match:
        return 100
    value = int(match.group())
    if value >= 30:
        return value  # already on the hundreds scale ("100L", "400")
    if program_type == "polytechnic" and "HND" in text:
        return (value + 2) * 100  # HND1 -> 300, HND2 -> 400
    return value * 100  # ND1 -> 100, NCE3 -> 300, year labels -> hundreds


def _base_stmt(course_code: str | None = None):
    stmt = (
        select(Course, _EFFECTIVE_UNIVERSITY.label("university_id"))
        .join(Department, Department.id == Course.department_id, isouter=True)
        .join(College, College.id == Department.college_id, isouter=True)
    )
    if course_code is not None:
        stmt = stmt.where(Course.code.ilike(course_code))
    return stmt


async def find_course(
    db: AsyncSession,
    course_code: str,
    university_id: str | None = None,
) -> tuple[Course, str | None] | None:
    """Resolve a course code for a viewer's institution.

    Own-institution rows win over shared legacy (NULL-university) rows; rows
    belonging to other institutions are never returned. Returns ``None`` when
    nothing matches.
    """
    stmt = _base_stmt(course_code)
    if university_id:
        stmt = stmt.where(
            or_(
                _EFFECTIVE_UNIVERSITY == university_id,
                _EFFECTIVE_UNIVERSITY.is_(None),
            )
        ).order_by(_EFFECTIVE_UNIVERSITY.is_(None))
    result = await db.execute(stmt.limit(1))
    row = result.first()
    if not row:
        return None
    course, effective_university_id = row
    return course, effective_university_id


async def course_exists_anywhere(
    db: AsyncSession, course_code: str
) -> tuple[str, str | None] | None:
    """Unscoped existence probe: (course_id, effective university) or None."""
    result = await db.execute(_base_stmt(course_code).limit(1))
    row = result.first()
    if not row:
        return None
    course, effective_university_id = row
    return course.id, effective_university_id


def course_visibility_filter(
    university_id: str | None,
) -> ColumnElement[bool] | None:
    """WHERE fragment restricting Course rows to a viewer's institution.

    Callers must include the Department/College outer joins in their statement
    for the coalesce expression to resolve. ``None`` means no restriction.
    """
    if not university_id:
        return None
    return or_(
        _EFFECTIVE_UNIVERSITY == university_id,
        _EFFECTIVE_UNIVERSITY.is_(None),
    )
