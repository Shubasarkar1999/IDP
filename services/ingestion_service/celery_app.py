from celery import Celery
from common.config.settings import settings

broker = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
backend = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1"

celery = Celery(
    "ingestion_tasks",
    broker=broker,
    backend=backend,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    result_expires=3600,
)

# ✅ Let Celery automatically discover tasks in this module
celery.autodiscover_tasks(["services.ingestion_service"])
