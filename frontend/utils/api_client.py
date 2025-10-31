import requests
import streamlit as st
import socket

#BASE_URL = "http://localhost:8000"  # ingestion_service
local_ip = socket.gethostbyname(socket.gethostname())
BASE_URL = f"http://{local_ip}:8000"

def upload_documents(files, branch_id, user_id):
    try:
        upload_url = f"{BASE_URL}/upload"
        files_data = [("files", (f.name, f, f.type)) for f in files]
        data = {"branch_id": branch_id, "user_id": user_id}
        resp = requests.post(upload_url, files=files_data, data=data, timeout=30)
        return resp.json()
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

def get_batch_status(batch_id: str):
    try:
        url = f"{BASE_URL}/batch_status/{batch_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"Failed to fetch status: {resp.status_code}")
            return None
    except Exception as e:
        st.error(f"Error fetching batch status: {e}")
        return None
