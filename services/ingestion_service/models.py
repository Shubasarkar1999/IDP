# services/ingestion_service/models.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, func
from .db import Base

class FileMetadata(Base):
    __tablename__ = "file_metadata"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(64), index=True, nullable=False)
    file_name = Column(String, nullable=False)
    minio_path = Column(String, nullable=False)
    uploader_id = Column(String(64), nullable=True)
    branch_id = Column(String(64), nullable=True)
    file_type = Column(String(64), nullable=True)   # e.g., aadhaar_front, pan, selfie
    size_bytes = Column(Integer, nullable=True)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    additional_meta = Column(JSON, nullable=True)
