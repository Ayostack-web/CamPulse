from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.postgres import get_connection
from app import plans

logger = logging.getLogger(__name__)
settings = get_settings()


def _run_async(coro):
    return asyncio.run(coro)


def _get_user_token(user_id: str) -> tuple[str, str | None]:
    """Get a valid Google access token, refreshing it if expired."""
    from app.services import google_drive

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT access_token, refresh_token, token_expires_at "
            "FROM connected_accounts WHERE user_id = %s AND provider = 'google'",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"No Google Drive connection for user {user_id}")

    access_token = row["access_token"]
    refresh_token = row.get("refresh_token")
    expires_at = row.get("token_expires_at")

    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            if not refresh_token:
                raise RuntimeError("Google Drive token expired, please reconnect")
            new_tokens = _run_async(google_drive.refresh_access_token(refresh_token))
            access_token = new_tokens.access_token
            new_expires = datetime.fromtimestamp(new_tokens.expires_at, tz=timezone.utc) if new_tokens.expires_at else None
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE connected_accounts SET access_token = %s, token_expires_at = %s "
                    "WHERE user_id = %s AND provider = 'google'",
                    (access_token, new_expires, user_id),
                )
                conn.commit()

    return access_token, refresh_token


def _file_already_imported(user_id: str, drive_file_id: str) -> bool:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM imported_files WHERE user_id = %s AND drive_file_id = %s",
            (user_id, drive_file_id),
        )
        return cur.fetchone() is not None


def _hash_file(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hash_exists(content_hash: str) -> str | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM materials WHERE content_hash = %s LIMIT 1",
            (content_hash,),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def _storage_used(user_id: str) -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(SUM(file_size), 0) AS total FROM materials WHERE uploader_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        return int(row["total"] or 0)


def _storage_allowance(user_id: str) -> int:
    """Mirror of ``entitlements.storage_allowance`` for the sync task context."""
    allowance = plans.FREE_STORAGE_BYTES
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT storage_bytes_total FROM subscriptions "
            "WHERE user_id = %s AND status = 'active' AND expires_at > NOW()",
            (user_id,),
        )
        for row in cur.fetchall():
            if row["storage_bytes_total"]:
                allowance = max(allowance, row["storage_bytes_total"])
    return allowance


def _ensure_content_hash_column() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("ALTER TABLE materials ADD COLUMN IF NOT EXISTS content_hash TEXT")
        conn.commit()


def _get_or_create_topic(course_id: str, title: str, user_id: str) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM topics WHERE course_id = %s AND is_active = true LIMIT 1",
            (course_id,),
        )
        row = cur.fetchone()
        if row:
            return row["id"]
        topic_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO topics (id, title, course_id, author_id, is_active, last_activity) "
            "VALUES (%s, %s, %s, %s, true, NOW())",
            (topic_id, title, course_id, user_id),
        )
        conn.commit()
        return topic_id


def _match_course(folder_name: str) -> str | None:
    match = re.search(r"([A-Za-z]{2,4}\d{3})", folder_name)
    if not match:
        return None
    code = match.group(1).upper()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM courses WHERE UPPER(code) = %s", (code,))
        row = cur.fetchone()
        return row["id"] if row else None


def _import_single(
    user_id: str, access_token: str, storage, file_id: str, topic_id: str, remaining: int
) -> tuple[str, int]:
    """Import one Google Drive file. Returns (status, bytes_stored).

    ``status`` is one of:
      - "imported"  — stored; ``bytes_stored`` is the size that now counts
        against the user's quota.
      - "duplicate" — content already in the vault; nothing new stored.
      - "already"   — this Drive file was imported before.
      - "quota"     — importing it would exceed the user's storage allowance.
    """
    from app.services import google_drive

    if _file_already_imported(user_id, file_id):
        return "already", 0

    file_meta = _run_async(google_drive.get_file_metadata(access_token, file_id))
    file_data = _run_async(google_drive.download_drive_file(access_token, file_id))

    from app.services.pdf_compressor import compress_pdf_bytes
    file_data = compress_pdf_bytes(file_data, file_meta.name)

    content_hash = _hash_file(file_data)

    existing = _file_hash_exists(content_hash)
    if existing:
        _create_import_record(
            user_id, file_id, file_meta.name, file_meta.mime_type,
            len(file_data), existing, "imported",
        )
        return "duplicate", 0

    if len(file_data) > remaining:
        return "quota", 0

    material_id = str(uuid.uuid4())
    ext = file_meta.name.split(".")[-1] if "." in file_meta.name else "pdf"
    storage_path = f"materials/{material_id}.{ext}"
    url = _run_async(
        storage.upload(settings.supabase_storage_bucket, storage_path, file_data, file_meta.mime_type)
    )

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO materials (id, file_name, file_url, file_path, file_size, topic_id, "
            "uploader_id, processing_status, is_shared, content_hash, uploaded_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'QUEUED',false,%s,NOW())",
            (material_id, file_meta.name, url, storage_path, len(file_data), topic_id, user_id, content_hash),
        )
        conn.commit()

    _create_import_record(
        user_id, file_id, file_meta.name, file_meta.mime_type,
        len(file_data), material_id, "imported",
    )
    return "imported", len(file_data)


def _create_import_record(
    user_id: str, drive_file_id: str, file_name: str, mime_type: str,
    file_size: int, material_id: str | None, status: str, error: str | None = None,
) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO imported_files (id, user_id, drive_file_id, file_name, mime_type, "
            "file_size, material_id, status, error, imported_at, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,"
            "CASE WHEN %s='imported' THEN NOW() END, NOW())",
            (str(uuid.uuid4()), user_id, drive_file_id, file_name, mime_type,
             file_size, material_id, status, error, status),
        )
        conn.commit()


# ── Celery Tasks ───────────────────────────────────────────────────


@celery_app.task(
    name="drive.import_files",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def import_drive_files(
    self, user_id: str, file_ids: list[str], topic_id: str,
) -> dict:
    """Import selected Google Drive files in the background."""
    from app.services.storage import get_storage

    _ensure_content_hash_column()
    storage = get_storage()
    imported = 0
    skipped = 0
    errors: list[str] = []

    try:
        access_token, _ = _get_user_token(user_id)
    except RuntimeError as e:
        return {"imported": 0, "skipped": 0, "errors": [str(e)]}

    remaining = _storage_allowance(user_id) - _storage_used(user_id)

    for file_id in file_ids[:20]:
        try:
            status, size = _import_single(user_id, access_token, storage, file_id, topic_id, remaining)
            if status == "imported":
                imported += 1
                remaining -= size
            elif status == "quota":
                _create_import_record(
                    user_id, file_id, f"quota_{file_id}", "unknown",
                    0, None, "failed", "STORAGE_LIMIT_REACHED",
                )
                errors.append(f"{file_id}: STORAGE_LIMIT_REACHED")
                break
            else:
                skipped += 1
        except Exception as e:
            logger.exception("Drive import failed for file %s", file_id)
            _create_import_record(
                user_id, file_id, f"failed_{file_id}", "unknown",
                0, None, "failed", str(e),
            )
            errors.append(f"{file_id}: {e}")

    return {"imported": imported, "skipped": skipped, "errors": errors}


@celery_app.task(
    name="drive.auto_import",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def auto_import_drive(self, user_id: str) -> dict:
    """Scan Google Drive, match folders to courses, import all PDFs."""
    from app.services import google_drive
    from app.services.storage import get_storage

    _ensure_content_hash_column()
    storage = get_storage()
    result = {
        "folders_scanned": 0, "pdfs_found": 0, "imported": 0,
        "skipped": 0, "topics_created": [], "errors": [],
    }

    try:
        access_token, _ = _get_user_token(user_id)
    except RuntimeError as e:
        result["errors"].append(str(e))
        return result

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM courses WHERE is_general = true LIMIT 1")
        row = cur.fetchone()
        if row:
            general_course_id = row["id"]
        else:
            general_course_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO courses (id, code, title, level, is_general) "
                "VALUES (%s, 'GEN', 'General Materials', 100, true)",
                (general_course_id,),
            )
            conn.commit()

    folders = _run_async(google_drive.list_drive_folders(access_token, "root"))
    result["folders_scanned"] = len(folders)

    remaining = _storage_allowance(user_id) - _storage_used(user_id)

    try:
        root_files, _ = _run_async(google_drive.list_drive_files(access_token, None, 100))
        for f in root_files:
            result["pdfs_found"] += 1
            topic_id = _get_or_create_topic(general_course_id, "Uncategorized", user_id)
            try:
                status, size = _import_single(user_id, access_token, storage, f.id, topic_id, remaining)
                if status == "imported":
                    result["imported"] += 1
                    remaining -= size
                elif status == "quota":
                    _create_import_record(
                        user_id, f.id, f.name, "unknown",
                        0, None, "failed", "STORAGE_LIMIT_REACHED",
                    )
                    result["errors"].append(f"{f.name}: storage limit reached")
                    return result
                else:
                    result["skipped"] += 1
            except Exception as e:
                result["errors"].append(f"{f.name}: {e}")
    except Exception:
        pass

    for folder in folders:
        try:
            files, _ = _run_async(google_drive.list_drive_files(access_token, folder.id, 100))
            result["pdfs_found"] += len(files)
            course_id = _match_course(folder.name) or general_course_id
            if not _match_course(folder.name):
                result["topics_created"].append(folder.name)
            topic_id = _get_or_create_topic(course_id, folder.name, user_id)
            for f in files:
                try:
                    status, size = _import_single(user_id, access_token, storage, f.id, topic_id, remaining)
                    if status == "imported":
                        result["imported"] += 1
                        remaining -= size
                    elif status == "quota":
                        _create_import_record(
                            user_id, f.id, f.name, "unknown",
                            0, None, "failed", "STORAGE_LIMIT_REACHED",
                        )
                        result["errors"].append(f"{f.name}: storage limit reached")
                        return result
                    else:
                        result["skipped"] += 1
                except Exception as e:
                    result["errors"].append(f"{f.name}: {e}")
        except Exception as e:
            result["errors"].append(f"Folder '{folder.name}': {e}")

    return result


@celery_app.task(name="drive.refresh_expiring_tokens")
def refresh_expiring_tokens() -> dict:
    """Proactively refresh Google tokens expiring within 10 minutes."""
    from app.services import google_drive

    refreshed = 0
    errors: list[str] = []
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=10)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT user_id, refresh_token, token_expires_at FROM connected_accounts "
            "WHERE provider = 'google' AND refresh_token IS NOT NULL "
            "AND token_expires_at IS NOT NULL AND token_expires_at < %s",
            (cutoff,),
        )
        accounts = cur.fetchall()

    for account in accounts:
        try:
            new_tokens = _run_async(google_drive.refresh_access_token(account["refresh_token"]))
            new_expires = datetime.fromtimestamp(new_tokens.expires_at, tz=timezone.utc) if new_tokens.expires_at else None
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE connected_accounts SET access_token = %s, token_expires_at = %s "
                    "WHERE user_id = %s AND provider = 'google'",
                    (new_tokens.access_token, new_expires, account["user_id"]),
                )
                conn.commit()
            refreshed += 1
        except Exception as e:
            logger.warning("Token refresh failed for user %s: %s", account["user_id"], e)
            errors.append(f"{account['user_id']}: {e}")

    return {"refreshed": refreshed, "errors": errors}
