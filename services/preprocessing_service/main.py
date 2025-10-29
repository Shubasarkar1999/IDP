# services/preprocessing_service/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from common.utils.logger import get_logger
from common.config.settings import settings
from .processor import process_single_object
import requests
import socket

logger = get_logger("preprocessing_service")
app = FastAPI(title="Preprocessing Service")

class ProcessItem(BaseModel):
    object_path: str  # like "documents/batchid/filename.pdf"

class ProcessBatchRequest(BaseModel):
    batch_id: str
    items: List[ProcessItem]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/process_batch")
def process_batch(req: ProcessBatchRequest):
    """
    Accepts JSON:
    {
      "batch_id": "uuid",
      "items": [{"object_path": "documents/.../file1.pdf"}, ...]
    }
    """
    batch_id = req.batch_id
    items = req.items
    if not items:
        raise HTTPException(status_code=400, detail="items empty")
    all_results = []
    # process sequentially (CPU)
    for it in items:
        try:
            res = process_single_object(it.object_path, batch_id)
            all_results.extend(res)
        except Exception as e:
            logger.exception(f"Failed processing {it.object_path}: {e}")
            all_results.append({"original": it.object_path, "error": str(e)})

    # After processing, call ingestion service callback to update metadata
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        callback_url= f"http://{local_ip}:8000/preprocess_callback"        
        payload = {
            "batch_id": batch_id,
            "results": all_results
        }
        r = requests.post(callback_url, json=payload, timeout=10)
        logger.info(f"Callback to ingestion service status: {r.status_code}")
    except Exception as e:
        logger.warning(f"Failed to call ingestion callback: {e}")

    return {"batch_id": batch_id, "processed": len(all_results), "details": all_results}
