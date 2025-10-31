from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database Configuration
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASS: str

    # MinIO Configuration
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    minio_public_url: str  


    # Redis Configuration
    REDIS_HOST: str
    REDIS_PORT: int

    # Environment
    ENV: str = "development"

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return (    
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Initialize settings
settings = Settings()
