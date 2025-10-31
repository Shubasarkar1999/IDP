from minio import Minio
from common.config.settings import settings
from datetime import timedelta
import os, sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

def get_client():
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False
    )

def get_presigned_url(path: str) -> str:
    """Generate a browser-accessible presigned URL."""
    try:
        if "/" not in path:
            return None

        bucket, object_name = path.split("/", 1)
        client = get_client()
        url = client.presigned_get_object(bucket, object_name, expires=timedelta(hours=2))

        # ✅ Replace internal Docker hostname (like "minio:9000") with public URL
        public_base = os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000")
        if settings.MINIO_ENDPOINT not in public_base:
            url = url.replace(f"http://{settings.MINIO_ENDPOINT}", public_base)

        return url
    except Exception as e:
        print(f"Presigned URL error: {e}")
        return None
