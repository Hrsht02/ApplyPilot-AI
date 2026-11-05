from celery import Celery
from app.config import settings

celery_app = Celery(
    "applypilot", broker=settings.redis_url, backend=settings.redis_url,
    include=["app.worker.tasks"]
)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True, broker_connection_retry_on_startup=True,
)
