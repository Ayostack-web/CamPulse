from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "vylix_ai_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks", "app.tasks_retention", "app.tasks_drive", "app.tasks_solvedbank"],
)

celery_app.conf.task_track_started = True
celery_app.conf.timezone = "UTC"
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_result_expires = 3600
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.broker_connection_retry_on_startup = True

celery_app.conf.beat_schedule = {
    "streak-reminders": {
        "task": "retention.streak_reminders",
        "schedule": crontab(hour=20, minute=0),
    },
    "new-material-alerts": {
        "task": "retention.new_material_alerts",
        "schedule": crontab(minute="*/30"),
    },
    "weekly-digest": {
        "task": "retention.weekly_digest",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
    },
    "active-user-count": {
        "task": "retention.update_active_counts",
        "schedule": crontab(minute="*/5"),
    },
    "refresh-expiring-tokens": {
        "task": "drive.refresh_expiring_tokens",
        "schedule": crontab(minute="*/10"),
    },
    "solved-bank-refill": {
        "task": "solvedbank.refill_all",
        "schedule": crontab(hour=2, minute=30, day_of_week=1),
    },
}
