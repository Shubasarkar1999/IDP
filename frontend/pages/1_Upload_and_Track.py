import streamlit as st
from utils.api_client import upload_documents, get_batch_status

st.set_page_config(page_title="Upload & Track", page_icon="📤")
st.title("📤 Upload and Track Documents")

branch_id = st.text_input("🏦 Branch ID", "BR001")
user_id = st.text_input("👤 User ID", "USR123")
files = st.file_uploader("📁 Upload PDF or Image files", type=["pdf", "jpg", "png", "jpeg", "doc", "docx"], accept_multiple_files=True)

if st.button("🚀 Upload and Process"):
    if not files:
        st.warning("Please upload at least one document.")
    else:
        with st.spinner("Uploading and initiating preprocessing..."):
            response = upload_documents(files, branch_id, user_id)
        if response and "batch_id" in response:
            st.session_state["batch_id"] = response["batch_id"]
            st.success(f"Upload successful! Batch ID: {response['batch_id']}")
        else:
            st.error("Upload failed. Check backend logs.")

st.divider()
st.subheader("📊 Track Processing Status")

batch_id = st.text_input("Enter Batch ID to check status", st.session_state.get("batch_id", ""))

if st.button("🔍 Check Status"):
    if not batch_id:
        st.warning("Enter a valid Batch ID")
    else:
        status = get_batch_status(batch_id)
        if status:
            st.json(status)
        else:
            st.error("No details found for this batch.")
