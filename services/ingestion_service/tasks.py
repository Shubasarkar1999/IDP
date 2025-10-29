# services/ingestion_service/tasks.py
from .celery_app import celery
from common.utils.logger import get_logger
import requests
import socket

logger = get_logger("ingestion_tasks")

@celery.task(bind=True)
def preprocess_job(self, batch_id: str, files: list):
    """
    Calls preprocessing_service /process_batch endpoint.
    """
    logger.info(f"preprocess_job: calling preprocessing_service for batch {batch_id}")
    local_ip = socket.gethostbyname(socket.gethostname())
    url = f"http://{local_ip}:8100/process_batch"
    payload = {
        "batch_id": batch_id,
        "items": [{"object_path": p} for p in files]
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        logger.info(f"preprocessing_service responded: {r.status_code}")
        return {"status": "submitted", "response": r.json()}
    except Exception as e:
        logger.exception("Failed to call preprocessing_service")
        raise
