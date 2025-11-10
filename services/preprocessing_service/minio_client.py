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

def download_object(bucket_object_path: str) -> bytes:
    if "/" not in bucket_object_path:
        raise ValueError("Invalid object path")
    bucket, object_name = bucket_object_path.split("/", 1)
    client = get_minio_client()
    resp = client.get_object(bucket, object_name)
    data = resp.read()
    resp.close()
    resp.release_conn()
    return data

def upload_bytes(bucket: str, object_name: str, data_bytes: bytes, content_type: str = "application/octet-stream"):
    client = get_minio_client()
    stream = BytesIO(data_bytes)
    stream.seek(0)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=stream,
        length=len(data_bytes),
        content_type=content_type
    )
    return f"{bucket}/{object_name}"
