# services/ingestion_service/init_db.py
from services.ingestion_service.db import engine, Base
from services.ingestion_service.models import FileMetadata


def init():
    Base.metadata.create_all(bind=engine)
    print("DB tables created")

if __name__ == "__main__":
    init()
