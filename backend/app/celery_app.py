from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "etsy_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.health",
        "app.tasks.seo",
        "app.tasks.sync",
        "app.tasks.agent",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Beat schedule — run under `celery beat -S redbeat.RedBeatScheduler`.
# The daily agent fans out to every eligible store at 07:00 UTC.
celery_app.conf.beat_schedule = {
    "daily-agent-fan-out": {
        "task": "tasks.agent.daily_agent_fan_out",
        "schedule": crontab(hour=7, minute=0),
    },
}
