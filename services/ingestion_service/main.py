# services/ingestion_service/main.py
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Optional
from common.utils.logger import get_logger
from common.config.settings import settings
from .minio_client import upload_bytes
from .db import SessionLocal
from .models import FileMetadata
from .tasks import preprocess_job
import mimetypes
from fastapi import Body

app = FastAPI(title="Ingestion Service")
logger = get_logger("ingestion_service")

ALLOWED_MIMES = {
    "image/jpeg", "image/png", "application/pdf", "image/jpg"
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per file (tweak as needed)

@app.get("/health")
def health_check():
    logger.info("Health check called")
    return {"status": "ok"}

@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    branch_id: Optional[str] = Form(None),
    uploader_id: Optional[str] = Form(None),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    batch_id = str(uuid.uuid4())
    saved_records = []

    db = SessionLocal()
    try:
        for f in files:
            content = await f.read()
            size = len(content)
            # size limit
            if size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(status_code=400, detail=f"File {f.filename} exceeds size limit")

            # mime check (try to guess if not provided)
            content_type = f.content_type or mimetypes.guess_type(f.filename)[0]
            if content_type not in ALLOWED_MIMES:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type} ({f.filename})")

            # create unique object name
            object_name = f"{batch_id}/{uuid.uuid4().hex}_{f.filename}"
            minio_path = upload_bytes(content, object_name, content_type)

            # determine file_type heuristically by filename (optional) - can be improved later
            file_type = None
            name_low = f.filename.lower()
            if "aadhaar" in name_low or "aadhar" in name_low:
                file_type = "aadhaar"
            elif "pan" in name_low:
                file_type = "pan"
            elif "selfie" in name_low or "photo" in name_low:
                file_type = "photo"
            else:
                file_type = "document"

            meta = FileMetadata(
                batch_id=batch_id,
                file_name=f.filename,
                minio_path=minio_path,
                uploader_id=uploader_id,
                branch_id=branch_id,
                file_type=file_type,
                size_bytes=size,
                additional_meta={"content_type": content_type}
            )
            db.add(meta)
            db.flush()  # get id if needed
            saved_records.append({
                "id": meta.id,
                "file_name": f.filename,
                "minio_path": minio_path,
                "file_type": file_type,
            })

        db.commit()

        # Launch background job (Celery)
        task = preprocess_job.delay(batch_id, [r["minio_path"] for r in saved_records])
        logger.info(f"Enqueued preprocess job {task.id} for batch {batch_id}")

        return JSONResponse({"batch_id": batch_id, "job_id": task.id, "files": saved_records})

    except Exception as e:
        db.rollback()
        logger.exception("Error during upload")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
        
@app.post("/preprocess_callback")
def preprocess_callback(payload: dict = Body(...)):
    """
    Called by preprocessing_service after preprocessing.
    Payload:
    {
      "batch_id": "...",
      "results": [
         {"original":"documents/..","enhanced":"documents/enhanced/..","page":1, ...},
         ...
      ]
    }
    """
    logger = get_logger("ingestion_service")
    logger.info(f"Preprocess callback for batch {payload.get('batch_id')}, items: {len(payload.get('results', []))}")
    # TODO: update DB records for file_metadata based on original path.
    # For now, we log and return success
    return {"status":"received", "batch_id": payload.get("batch_id")}