from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.postgres import get_connection

settings = get_settings()
logger = logging.getLogger(__name__)


def _create_notification(
    user_id: str,
    kind: str,
    title: str,
    message: str,
    payload: dict | None = None,
) -> None:
    import uuid
    query = """
        INSERT INTO notifications (id, user_id, kind, title, message, payload, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (str(uuid.uuid4()), user_id, kind, title, message, _json_dumps(payload)))
        conn.commit()


def _json_dumps(obj) -> str | None:
    if obj is None:
        return None
    import json
    return json.dumps(obj)


@celery_app.task(name="retention.streak_reminders")
def streak_reminders() -> str:
    """Send streak reminders to users who haven't checked in today."""
    query = """
        INSERT INTO notifications (id, user_id, kind, title, message, created_at)
        SELECT
            gen_random_uuid()::text,
            u.id,
            'streak_reminder',
            'Keep your streak alive!',
            CASE
                WHEN us.current_streak >= 7 THEN 'You have a ' || us.current_streak || '-day streak! Don''t break it now.'
                WHEN us.current_streak >= 3 THEN 'You''re on a ' || us.current_streak || '-day streak. Check in to keep it going!'
                ELSE 'Check in today to start building your streak!'
            END,
            NOW()
        FROM users u
        JOIN user_streaks us ON us.user_id = u.id
        WHERE us.current_streak > 0
          AND (us.last_activity_at < (NOW() - INTERVAL '16 hours'))
          AND u.last_active_at > (NOW() - INTERVAL '48 hours')
          AND NOT EXISTS (
              SELECT 1 FROM notifications n
              WHERE n.user_id = u.id
                AND n.kind = 'streak_reminder'
                AND n.created_at > (NOW() - INTERVAL '20 hours')
          )
        LIMIT 500
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query)
        count = cursor.rowcount
        conn.commit()

    logger.info("Streak reminders sent: %d", count)
    return f"sent {count} streak reminders"


@celery_app.task(name="retention.new_material_alerts")
def new_material_alerts() -> str:
    """Notify users when new materials are uploaded to their courses."""
    query = """
        WITH recent_materials AS (
            SELECT
                m.id AS material_id,
                m.file_name,
                m.uploader_id,
                t.course_id,
                c.code AS course_code,
                c.title AS course_title
            FROM materials m
            JOIN topics t ON t.id = m.topic_id
            JOIN courses c ON c.id = t.course_id
            WHERE m.uploaded_at > (NOW() - INTERVAL '35 minutes')
              AND m.processing_status != 'FAILED'
        ),
        course_department_users AS (
            SELECT DISTINCT
                rm.material_id,
                rm.file_name,
                rm.course_code,
                rm.course_title,
                u.id AS user_id
            FROM recent_materials rm
            JOIN courses c ON c.id = rm.course_id
            JOIN departments d ON d.id = c.department_id
            JOIN users u ON u.department_id = d.id
            WHERE u.id != rm.uploader_id
              AND u.last_active_at > (NOW() - INTERVAL '7 days')
        )
        INSERT INTO notifications (id, user_id, kind, title, message, payload, created_at)
        SELECT
            gen_random_uuid()::text,
            cdu.user_id,
            'new_material',
            'New material in ' || cdu.course_code,
            cdu.file_name || ' was just uploaded to ' || cdu.course_title,
            json_build_object(
                'material_id', cdu.material_id,
                'course_code', cdu.course_code
            )::text,
            NOW()
        FROM course_department_users cdu
        WHERE NOT EXISTS (
            SELECT 1 FROM notifications n
            WHERE n.user_id = cdu.user_id
              AND n.kind = 'new_material'
              AND n.message LIKE '%' || cdu.material_id || '%'
              AND n.created_at > (NOW() - INTERVAL '1 hour')
        )
        LIMIT 500
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query)
        count = cursor.rowcount
        conn.commit()

    logger.info("New material alerts sent: %d", count)
    return f"sent {count} new material alerts"


@celery_app.task(name="retention.weekly_digest")
def weekly_digest() -> str:
    """Send a weekly activity summary to active users."""
    query = """
        INSERT INTO notifications (id, user_id, kind, title, message, payload, created_at)
        SELECT
            gen_random_uuid()::text,
            u.id,
            'weekly_digest',
            'Your weekly summary',
            'This week: ' ||
                COALESCE(mat.material_count, 0) || ' materials uploaded, ' ||
                COALESCE(qna.question_count, 0) || ' questions asked, ' ||
                COALESCE(qna.answer_count, 0) || ' answers given. ' ||
                'Keep it up!',
            json_build_object(
                'materials_uploaded', COALESCE(mat.material_count, 0),
                'questions_asked', COALESCE(qna.question_count, 0),
                'answers_given', COALESCE(qna.answer_count, 0),
                'streak', COALESCE(us.current_streak, 0),
                'points', COALESCE(pts.total_points, 0)
            )::text,
            NOW()
        FROM users u
        LEFT JOIN user_streaks us ON us.user_id = u.id
        LEFT JOIN (
            SELECT uploader_id, COUNT(*) AS material_count
            FROM materials
            WHERE uploaded_at > (NOW() - INTERVAL '7 days')
            GROUP BY uploader_id
        ) mat ON mat.uploader_id = u.id
        LEFT JOIN (
            SELECT author_id, COUNT(*) AS question_count
            FROM topic_questions
            WHERE created_at > (NOW() - INTERVAL '7 days')
            GROUP BY author_id
        ) qna ON qna.author_id = u.id
        LEFT JOIN (
            SELECT user_id, SUM(amount) AS total_points
            FROM points_transactions
            WHERE created_at > (NOW() - INTERVAL '7 days')
            GROUP BY user_id
        ) pts ON pts.user_id = u.id
        WHERE u.last_active_at > (NOW() - INTERVAL '14 days')
          AND NOT EXISTS (
              SELECT 1 FROM notifications n
              WHERE n.user_id = u.id
                AND n.kind = 'weekly_digest'
                AND n.created_at > (NOW() - INTERVAL '6 days')
          )
        LIMIT 500
    """
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query)
        count = cursor.rowcount
        conn.commit()

    logger.info("Weekly digests sent: %d", count)
    return f"sent {count} weekly digests"


@celery_app.task(name="retention.update_active_counts")
def update_active_counts() -> str:
    """Update a simple Redis counter for active users (used by social presence)."""
    try:
        import redis
        # NOTE: must be the Redis URL (settings.redis_url, DB 0) — not the
        # broker/backend URLs, which use separate logical DBs.
        r = redis.from_url(settings.redis_url)
        five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE last_active_at > %s",
                (five_min_ago,),
            )
            count = cursor.fetchone()[0]
        r.set("vylix:active_users", count, ex=300)
        logger.info("Active user count updated: %d", count)
        return f"active users: {count}"
    except Exception:
        logger.exception("Failed to update active user count")
        return "failed"
