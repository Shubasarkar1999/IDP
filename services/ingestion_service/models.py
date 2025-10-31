from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from .db import Base

class FileMetadata(Base):
    __tablename__ = "file_metadata"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, index=True)
    file_name = Column(String)
    minio_path = Column(String, unique=True)
    uploader_id = Column(String, nullable=True)
    branch_id = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    size_bytes = Column(Integer)
    status = Column(String, default="uploaded")  # ✅ <-- ADD THIS LINE
    additional_meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
