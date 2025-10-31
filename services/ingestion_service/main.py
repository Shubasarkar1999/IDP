# services/ingestion_service/main.py
import uuid
import mimetypes
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import JSONResponse
from typing import List, Optional
from common.utils.logger import get_logger
from common.config.settings import settings
from .minio_client import upload_bytes
from .db import SessionLocal
from .models import FileMetadata
from .tasks import preprocess_job

app = FastAPI(title="Ingestion Service")
logger = get_logger("ingestion_service")

ALLOWED_MIMES = {"image/jpeg", "image/png", "application/pdf", "image/jpg"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

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

            # size limit check
            if size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(status_code=400, detail=f"File {f.filename} exceeds size limit")

            # detect MIME type
            content_type = f.content_type or mimetypes.guess_type(f.filename)[0]
            if content_type not in ALLOWED_MIMES:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type} ({f.filename})")

            # upload to MinIO
            object_name = f"{batch_id}/{uuid.uuid4().hex}_{f.filename}"
            minio_path = upload_bytes(content, object_name, content_type)

            # determine file type
            mime_type, _ = mimetypes.guess_type(f.filename)
            file_type = mime_type.split("/")[0] if mime_type else "unknown"

            name_low = f.filename.lower()
            if "aadhaar" in name_low or "aadhar" in name_low:
                file_type = "aadhaar"
            elif "pan" in name_low:
                file_type = "pan"
            elif "selfie" in name_low or "photo" in name_low:
                file_type = "photo"

            meta = FileMetadata(
                batch_id=batch_id,
                file_name=f.filename,
                minio_path=minio_path,
                uploader_id=uploader_id,
                branch_id=branch_id,
                file_type=file_type,
                size_bytes=size,
                status="uploaded",
                additional_meta={"content_type": content_type},
            )
            db.add(meta)
            db.flush()
            saved_records.append({
                "id": meta.id,
                "file_name": f.filename,
                "file_type": file_type,
                "status": meta.status,
                "minio_path": minio_path,
            })

        db.commit()

        # Automatically trigger enhancement (Celery)
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
    Called by preprocessing_service after enhancement.
    Example payload:
    {
        "batch_id": "...",
        "results": [
            {"original": "documents/...jpg", "enhanced": "documents/enhanced/...jpg"}
        ]
    }
    """
    db = SessionLocal()
    try:
        batch_id = payload.get("batch_id")
        results = payload.get("results", [])
        logger.info(f"Preprocess callback received for {batch_id}")

        updated = 0
        for r in results:
            original_path = r.get("original")
            enhanced_path = r.get("enhanced")

            if not original_path or not enhanced_path:
                continue

            # Try exact match first
            record = db.query(FileMetadata).filter(FileMetadata.minio_path == original_path).first()

            # Fallback: try partial match (for cases where path prefixes differ)
            if not record:
                record = (
                    db.query(FileMetadata)
                    .filter(FileMetadata.minio_path.ilike(f"%{original_path.split('/')[-1]}"))
                    .first()
                )

            if record:
                record.status = "enhanced"
                record.additional_meta = record.additional_meta or {}
                record.additional_meta["enhanced_path"] = enhanced_path
                db.add(record)
                updated += 1
            else:
                logger.warning(f"No match found in DB for {original_path}")

        db.commit()
        logger.info(f"Callback updated {updated} records for batch {batch_id}")

        return {"status": "success", "batch_id": batch_id, "updated_records": updated}
    except Exception as e:
        db.rollback()
        logger.exception("Error in preprocess callback")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/batch_status/{batch_id}")
def batch_status(batch_id: str):
    """Return all files and their enhancement status for a given batch."""
    db = SessionLocal()
    try:
        records = db.query(FileMetadata).filter(FileMetadata.batch_id == batch_id).all()
        if not records:
            raise HTTPException(status_code=404, detail="Batch not found")

        result = []
        for r in records:
            result.append({
                "id": r.id,
                "file_name": r.file_name,
                "file_type": r.file_type,
                "status": r.status,
                "minio_path": r.minio_path,
                "enhanced_path": (r.additional_meta or {}).get("enhanced_path"),
                "uploaded_at": str(r.created_at),
            })
        return {"batch_id": batch_id, "files": result}
    except Exception as e:
        logger.exception("Error fetching batch status")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
