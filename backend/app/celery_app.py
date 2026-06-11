from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "etsy_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.health"],
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
