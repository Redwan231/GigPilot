"""Celery application factory (04_TRD §6)."""

from celery import Celery

from app.config import settings

celery = Celery("gigpilot", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_max_tasks_per_child=100,
)

celery.autodiscover_tasks(["app.workers"])
