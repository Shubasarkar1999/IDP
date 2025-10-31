# streamlit_app.py
import streamlit as st
from utils.api_client import upload_documents, get_batch_status
from utils.minio_presigned import get_presigned_url
from dotenv import load_dotenv
import sys
import os

# Ensure root directory is in Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR,".env"))
st.set_page_config(page_title="Document Uploader", page_icon="📄")

st.title("📤 Document Uploader & Enhancer")

# --- Upload Section ---
branch_id = st.text_input("🏦 Branch ID", "BR001")
user_id = st.text_input("👤 User ID", "USR123")
files = st.file_uploader("📁 Upload PDF or Image files", type=["pdf", "jpg", "png", "jpeg"], accept_multiple_files=True)

if st.button("🚀 Upload & Start Enhancement"):
    if not files:
        st.warning("Please upload at least one document.")
    else:
        with st.spinner("Uploading files and starting enhancement..."):
            response = upload_documents(files, branch_id, user_id)
        if response and "batch_id" in response:
            st.session_state["batch_id"] = response["batch_id"]
            st.success(f"✅ Upload successful! Batch ID: {response['batch_id']}")
        else:
            st.error("❌ Upload failed. Check backend logs.")

st.divider()

# --- Status Section ---
st.subheader("📊 Track Enhancement Status")

batch_id = st.text_input("Enter Batch ID", st.session_state.get("batch_id", ""))

if st.button("🔍 Check Status"):
    if not batch_id:
        st.warning("Enter a valid Batch ID")
    else:
        with st.spinner("Fetching batch status..."):
            data = get_batch_status(batch_id)
        if not data or "files" not in data:
            st.error("No details found for this batch.")
        else:
            for f in data["files"]:
                st.write(f"**{f['file_name']}** — Status: `{f['status']}`")
                if f["status"] == "enhanced" and f.get("enhanced_path"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.image(get_presigned_url(f["minio_path"]), caption="🧾 Original")
                    with col2:
                        st.image(get_presigned_url(f["enhanced_path"]), caption="✨ Enhanced")
