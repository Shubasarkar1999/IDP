# services/ingestion_service/create_bucket.py
from minio import Minio
from common.config.settings import settings

def create_bucket():
    client = Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False
    )
    bucket = settings.MINIO_BUCKET
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"Bucket '{bucket}' created.")
    else:
        print(f"Bucket '{bucket}' already exists.")

if __name__ == "__main__":
    create_bucket()
