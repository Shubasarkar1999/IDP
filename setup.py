from setuptools import setup, find_packages

setup(
    name="docintel",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi",
        "sqlalchemy",
        "psycopg2-binary",
        "alembic",
        "uvicorn",
        "minio",
        "requests",
        "pydantic",
        "pandas",
        "streamlit",
        "Pillow",
    ],
)
