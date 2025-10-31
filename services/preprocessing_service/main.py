from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from common.utils.logger import get_logger
from .minio_client import download_object, upload_bytes
from .processor.converter import pdf_to_images
from .processor.enhancer import enhance_image
from .processor.classifier import classify_document
import requests
import socket
import tempfile
import os
import io

logger = get_logger("preprocessing_service")
app = FastAPI(title="Preprocessing Service")


class ProcessItem(BaseModel):
    object_path: str


class ProcessBatchRequest(BaseModel):
    batch_id: str
    items: List[ProcessItem]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process_batch")
def process_batch(req: ProcessBatchRequest):
    batch_id = req.batch_id
    items = req.items
    if not items:
        raise HTTPException(status_code=400, detail="items empty")

    results = []

    for item in items:
        object_path = item.object_path
        try:
            logger.info(f"Processing file: {object_path}")

            # --- Step 1: Download file from MinIO ---
            data = download_object(object_path)
            tmp_input = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(object_path)[-1])
            tmp_input.write(data)
            tmp_input.flush()

            # --- Step 2: Convert to images if PDF ---
            if object_path.lower().endswith(".pdf"):
                image_paths = pdf_to_images(tmp_input.name)
            else:
                image_paths = [tmp_input.name]

            # --- Step 3: Process each image ---
            processed_files = []
            for img_path in image_paths:
                # 🧩 Extract original filename from the MinIO path, not temp file
                original_file_name = os.path.basename(object_path)
                base_name, original_ext = os.path.splitext(original_file_name)

                # --- Enhance image ---
                enhanced_bytes = enhance_image(img_path)

                # ✅ Use same base name for enhanced version (fix)
                enhanced_name = f"{base_name}_enhanced{original_ext}"

                # ✅ Store inside correct folder structure
                bucket = "documents"
                enhanced_object_path = f"enhanced/{batch_id}/{enhanced_name}"

                # --- Upload enhanced image ---
                uploaded_path = upload_bytes(
                    bucket=bucket,
                    object_name=enhanced_object_path,
                    data_bytes=enhanced_bytes,
                    content_type="image/jpeg" if original_ext.lower() in [".jpg", ".jpeg"] else "image/png"
                )

                logger.info(f"✅ Uploaded enhanced image to: {uploaded_path}")

                # --- Step 4: Classify enhanced image ---
                doc_type, confidence = classify_document(img_path)

                processed_files.append({
                    "input": object_path,
                    "enhanced_path": f"{bucket}/{enhanced_object_path}",  # ✅ include full enhanced path
                    "type": doc_type,
                    "confidence": confidence
                })

            results.extend(processed_files)

        except Exception as e:
            logger.exception(f"Failed processing {object_path}: {e}")
            results.append({"original": object_path, "error": str(e)})

    # --- Step 5: Send callback to ingestion service ---
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        callback_url = f"http://{local_ip}:8000/preprocess_callback"
        payload = {"batch_id": batch_id, "results": results}
        r = requests.post(callback_url, json=payload, timeout=10)
        logger.info(f"Callback response from ingestion: {r.status_code}")
    except Exception as e:
        logger.warning(f"Callback failed: {e}")

    return {"batch_id": batch_id, "processed": len(results), "details": results}
