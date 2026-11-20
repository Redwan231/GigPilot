"""Celery beat schedule (04_TRD §6). Aggregation runs every 30 minutes."""

from celery.schedules import crontab

from app.workers.celery_app import celery

celery.conf.beat_schedule = {
    "aggregate-jobs-every-30m": {
        "task": "app.workers.tasks.aggregate_jobs",
        "schedule": crontab(minute="*/30"),
    },
}
