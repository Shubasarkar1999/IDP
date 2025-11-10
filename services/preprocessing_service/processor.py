import io
import os
import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from skimage import img_as_ubyte
from skimage.restoration import wiener
from skimage.color import rgb2gray
from PyPDF2 import PdfMerger
from common.utils.logger import get_logger
from .minio_client import download_object, upload_bytes
from common.config.settings import settings
import cv2
import tempfile

logger = get_logger("preprocessing_processor")

# ---------------- IMAGE HELPERS ----------------

def pdf_bytes_to_images(pdf_bytes: bytes) -> list[Image.Image]:
    """Convert PDF bytes to list of PIL images (one per page)."""
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
    return images


def pil_to_cv(img: Image.Image):
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def cv_to_pil(img: np.ndarray):
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def deskew_image_pil(img: Image.Image) -> Image.Image:
    cv = pil_to_cv(img)
    gray = cv2.cvtColor(cv, cv2.COLOR_BGR2GRAY)
    coords = np.column_stack(np.where(gray < 255))
    if coords.size == 0:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = cv.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(cv, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return cv_to_pil(rotated)


def contrast_clahe_pil(img: Image.Image) -> Image.Image:
    cv = pil_to_cv(img)
    lab = cv2.cvtColor(cv, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    final = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    return cv_to_pil(final)


def simple_wiener_deblur_pil(img: Image.Image) -> Image.Image:
    arr = np.array(img).astype(np.float32)
    if arr.ndim == 3:
        arr_gray = rgb2gray(arr)
    else:
        arr_gray = arr
    psf = np.ones((3, 3)) / 9.0
    try:
        deconvolved = wiener(arr_gray, psf, balance=0.1)
        out = img_as_ubyte(deconvolved)
        return Image.fromarray(out).convert("RGB")
    except Exception as e:
        logger.warning(f"Wiener deblur failed: {e}")
        return img


def enhance_image_pipeline(img: Image.Image) -> Image.Image:
    try:
        img = deskew_image_pil(img)
    except Exception as e:
        logger.warning(f"Deskew failed: {e}")
    try:
        img = contrast_clahe_pil(img)
    except Exception as e:
        logger.warning(f"CLAHE failed: {e}")
    try:
        img = simple_wiener_deblur_pil(img)
    except Exception as e:
        logger.warning(f"Deblur failed: {e}")

    max_w = 1800
    if img.width > max_w:
        ratio = max_w / img.width
        new_h = int(img.height * ratio)
        img = img.resize((max_w, new_h), Image.LANCZOS)
    return img

# ---------------- MAIN PROCESSOR ----------------

def process_single_object(bucket_object_path: str, batch_id: str) -> list[dict]:
    """
    Handles:
      - Detect if file is PDF or Image
      - Convert PDF to per-page images
      - Enhance each page
      - Merge enhanced images → single PDF
      - Upload enhanced images + PDF to MinIO
    """
    logger.info(f"Processing file: {bucket_object_path}")

    data = download_object(bucket_object_path)
    is_pdf = bucket_object_path.lower().endswith(".pdf")

    # Step 1: Extract pages as PIL images
    if is_pdf:
        images = pdf_bytes_to_images(data)
    else:
        images = [Image.open(io.BytesIO(data)).convert("RGB")]

    _, object_name = bucket_object_path.split("/", 1)
    base_filename = os.path.basename(object_name).split(".")[0]

    enhanced_image_paths = []
    results = []

    # Step 2: Enhance & upload per page as PNG
    for i, img in enumerate(images, start=1):
        enhanced = enhance_image_pipeline(img)
        buf = io.BytesIO()
        enhanced.save(buf, format="PNG", optimize=True)
        buf_bytes = buf.getvalue()

        enhanced_name = f"{base_filename}_page{i:03d}_enhanced.png"
        enhanced_object_path = f"documents/enhanced/{batch_id}/{enhanced_name}"

        uploaded = upload_bytes(
            bucket=settings.MINIO_BUCKET,
            object_name=enhanced_object_path,
            data_bytes=buf_bytes,
            content_type="image/png"
        )

        enhanced_image_paths.append(uploaded)
        results.append({
            "page": i,
            "enhanced_image": uploaded,
            "size_bytes": len(buf_bytes)
        })

    logger.info(f"✅ Uploaded enhanced page {i} to: {uploaded}")

    # Step 3: Merge enhanced images into single enhanced PDF
    if is_pdf and results:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix="_enhanced.pdf") as temp_pdf:
                # Use in-memory enhanced images (avoid re-downloading from MinIO)
                pil_pages = []
                for page_info in results:
                    if "enhanced_image" in page_info:
                        img_bytes = io.BytesIO(download_object(page_info["enhanced_image"]))
                        pil_img = Image.open(img_bytes).convert("RGB")
                        pil_pages.append(pil_img)

                if not pil_pages:
                    logger.warning("⚠️ No enhanced pages to merge.")
                else:
                    pil_pages[0].save(
                        temp_pdf.name,
                        save_all=True,
                        append_images=pil_pages[1:],
                        format="PDF",
                        resolution=150,
                        optimize=True
                    )

                # Read merged PDF bytes
                pdf_bytes = open(temp_pdf.name, "rb").read()
                enhanced_pdf_path = f"documents/enhanced/{batch_id}/{base_filename}_enhanced.pdf"

                uploaded_pdf = upload_bytes(
                    bucket=settings.MINIO_BUCKET,
                    object_name=enhanced_pdf_path,
                    data_bytes=pdf_bytes,
                    content_type="application/pdf"
                )

                logger.info(f"✅ Uploaded merged enhanced PDF: {uploaded_pdf}")
                results.append({
                    "enhanced_pdf": uploaded_pdf,
                    "pages": len(pil_pages)
                })

        except Exception as e:
            logger.error(f"❌ PDF merge failed: {e}")

        return results
