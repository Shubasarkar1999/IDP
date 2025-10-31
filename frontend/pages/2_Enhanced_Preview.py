import streamlit as st
from utils.api_client import get_batch_status
from utils.minio_presigned import get_presigned_url
import urllib.parse
import os

st.set_page_config(page_title="Enhanced Preview", page_icon="🖼️")
st.title("🖼️ Enhanced Document Preview")

batch_id = st.text_input("Enter Batch ID", st.session_state.get("batch_id", ""))

if st.button("🔍 Load Enhanced Documents"):
    if not batch_id:
        st.warning("Please enter a Batch ID first.")
    else:
        with st.spinner("Fetching enhanced documents..."):
            data = get_batch_status(batch_id)
            if not data or "files" not in data:
                st.error("No data found for this batch.")
            else:
                for f in data["files"]:
                    file_name = f.get("file_name", "unknown file")
                    minio_path = f.get("minio_path")
                    enhanced_path = f.get("enhanced_path")

                    st.write(f"🧩 Original MinIO path: {minio_path}")
                    st.write(f"🧩 Reported enhanced path: {enhanced_path}")

                    possible_paths = []

                    # --- Try building enhanced path intelligently ---
                    if not enhanced_path and minio_path and batch_id in minio_path:
                        bucket, rest = minio_path.split("/", 1)
                        # Example rest: "d65b1fcc-417c-4446-b0b7-3be346abf31e/c13cf8c6ac30445b88c9743fff62903b_aadhar_back.jpg"
                        base_name = os.path.basename(rest)
                        base_name_no_ext, ext = os.path.splitext(base_name)

                        # Extract prefix (UUID) and actual name part
                        parts = base_name_no_ext.split("_", 1)
                        prefix = ""
                        main_name = base_name_no_ext
                        if len(parts) == 2:
                            prefix = parts[0]
                            main_name = parts[1]

                        # Try multiple image extensions
                        possible_exts = ["jpg", "jpeg", "png"]

                        for e in possible_exts:
                            # Build correct enhanced file name (including prefix)
                            if prefix:
                                possible_paths.append(
                                    f"documents/enhanced/{batch_id}/{prefix}_{main_name}_enhanced.{e}"
                                )
                            # Fallback without prefix
                            possible_paths.append(
                                f"documents/enhanced/{batch_id}/{main_name}_enhanced.{e}"
                            )
                    else:
                        possible_paths = [enhanced_path]

                    # --- Encode/Decode paths for URL safety ---
                    path_candidates = []
                    for path in possible_paths:
                        if not path:
                            continue
                        decoded = urllib.parse.unquote(path)
                        encoded = urllib.parse.quote(decoded, safe="/")
                        path_candidates.extend([decoded, encoded])

                    st.write("🔍 Checking possible enhanced paths:")
                    for p in path_candidates:
                        st.write(f"   - {p}")

                    # --- Fetch URLs ---
                    orig_url = get_presigned_url(minio_path)
                    enh_url = None
                    for p in path_candidates:
                        enh_url = get_presigned_url(p)
                        if enh_url:
                            st.write(f"✅ Found valid enhanced URL: {p}")
                            break

                    # 🧾 DEBUG URLs
                    st.write("🧾 Presigned Original URL:", orig_url)
                    st.write("✨ Presigned Enhanced URL:", enh_url)

                    # --- Display Images ---
                    col1, col2 = st.columns(2)
                    with col1:
                        if orig_url:
                            st.image(orig_url, caption=f"🧾 Original - {file_name}")
                    with col2:
                        if enh_url:
                            st.image(enh_url, caption=f"✨ Enhanced - {file_name}")
                        else:
                            st.warning(f"⚠️ Enhanced image not found for {file_name}")
