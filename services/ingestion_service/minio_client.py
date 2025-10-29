# services/ingestion_service/minio_client.py
from minio import Minio
from io import BytesIO
from common.config.settings import settings

def get_minio_client():
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False
    )

def upload_bytes(file_bytes: bytes, object_name: str, content_type: str):
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET
    # put_object expects a stream (BytesIO) or file path
    stream = BytesIO(file_bytes)
    stream.seek(0)
    client.put_object(bucket_name=bucket, object_name=object_name, data=stream, length=len(file_bytes), content_type=content_type)
    return f"{bucket}/{object_name}"
