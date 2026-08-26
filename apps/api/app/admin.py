"""Admin authentication dependency.

Checks that the current user has ``role == 'admin'``.  If the user's email
is listed in ``ADMIN_EMAILS`` and their role is still ``'student'``, they
are auto-promoted to ``'admin'`` on first check (handles first-login
bootstrap without a separate migration step).

Usage::

    from app.admin import require_admin, AdminUser

    @router.get("/admin/secret")
    async def secret(admin: AdminUser = Depends(require_admin)):
        ...
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.models import User

logger = logging.getLogger(__name__)


@dataclass
class AdminUser:
    id: str
    email: str | None
    full_name: str | None
    user: User


def _admin_emails_set() -> set[str]:
    settings = get_settings()
    return {
        e.strip().lower()
        for e in settings.admin_emails.split(",")
        if e.strip()
    }


async def require_admin(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """FastAPI dependency: 403 unless user is admin.

    Auto-promotes users whose email is in ADMIN_EMAILS on first check.
    """
    # Auto-promote if email is in ADMIN_EMAILS and role is still 'student'
    email_lower = (current.email or "").lower()
    if email_lower and current.user.role == "student" and email_lower in _admin_emails_set():
        current.user.role = "admin"
        await db.flush()
        logger.info("Auto-promoted %s to admin", email_lower)

    if current.user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return AdminUser(
        id=current.id,
        email=current.email,
        full_name=current.full_name,
        user=current.user,
    )
