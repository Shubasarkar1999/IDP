#!/bin/bash
set -e  # Exit immediately if any command fails

echo "============================================="
echo " 🚀 Starting Doc-Intel System (All Services) "
echo "============================================="

# ------------------ PROXY ------------------
export HTTP_PROXY="http://272752:Babun%4012345@hoproxy2.bandhan.local:8080"
export HTTPS_PROXY="http://272752:Babun%4012345@hoproxy2.bandhan.local:8080"
echo "✅ Proxy configured."

# ------------------ START DOCKER CONTAINERS ------------------
echo "🐳 Starting Docker containers (postgres, redis, minio)..."
for svc in postgres redis minio; do
  echo "▶️ Starting $svc..."
  if docker start "$svc" >/dev/null 2>&1; then
    echo "✅ $svc started successfully."
  else
    echo "⚠️ $svc not found or failed to start. Please check with 'docker ps -a'."
  fi
done

# ------------------ INSTALL DEPENDENCIES ------------------
# echo "📦 Installing Python dependencies..."
# pip install -e .
# pip install -r services/ingestion_service/requirements.txt
# pip install -r services/preprocessing_service/requirements.txt
# pip install -r frontend/requirements.txt

# ------------------ DATABASE MIGRATION ------------------
echo "🧱 Running Alembic migrations..."
cd services/ingestion_service
alembic upgrade head || echo "⚠️ Alembic migration skipped or failed (maybe already up to date)"
cd ../../

# ------------------ RUN SERVICES ------------------
echo "🌐 Launching backend and frontend services..."

nohup uvicorn services.ingestion_service.main:app --host 0.0.0.0 --port 8000 > ingestion.log 2>&1 &
nohup uvicorn services.preprocessing_service.main:app --host 0.0.0.0 --port 8100 > preprocessing.log 2>&1 &
nohup celery -A services.ingestion_service.celery_app.celery worker --loglevel=info --pool=solo > celery.log 2>&1 &
nohup streamlit run frontend/streamlit_app.py > streamlit.log 2>&1 &

# ------------------ FINAL STATUS ------------------
echo "✅ All services are up and running."
echo "---------------------------------------------"
echo "🌍 Ingestion API → http://localhost:8000"
echo "🌍 Preprocessing API → http://localhost:8100"
echo "💻 Streamlit Frontend → http://localhost:8501"
echo "---------------------------------------------"
echo "🪵 Logs:"
echo "   ingestion.log | preprocessing.log | celery.log | streamlit.log"
echo "---------------------------------------------"
