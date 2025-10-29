# services/preprocessing_service/processor.py
import fitz  # pymupdf
import io
import numpy as np
from PIL import Image, ImageOps
import cv2
from skimage.restoration import wiener
from skimage.color import rgb2gray
from skimage import img_as_ubyte
from typing import List, Tuple
from .minio_client import download_object, upload_bytes
from common.utils.logger import get_logger
from common.config.settings import settings

logger = get_logger("preprocessing_processor")

# ---------- Image utilities ----------

def pdf_bytes_to_images(pdf_bytes: bytes) -> List[Image.Image]:
    """Convert PDF bytes to list of PIL images (one per page)."""
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            # Render page at 150-200 dpi for CPU
            mat = fitz.Matrix(2, 2)  # about 150-200 dpi depending on page size
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
    return images

def pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def cv_to_pil(img: np.ndarray) -> Image.Image:
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(img_rgb)

def deskew_image_pil(img: Image.Image) -> Image.Image:
    # Convert to grayscale and compute angle via cv2
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
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    final = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    return cv_to_pil(final)

def simple_wiener_deblur_pil(img: Image.Image) -> Image.Image:
    # Convert to gray float
    arr = np.array(img).astype(np.float32)
    if arr.ndim == 3:
        arr_gray = rgb2gray(arr)
    else:
        arr_gray = arr
    # build tiny psf (point spread function) kernel
    psf = np.ones((3,3)) / 9.0
    try:
        deconvolved = wiener(arr_gray, psf, balance=0.1)
        # scale back to 0-255
        out = img_as_ubyte(deconvolved)
        pil = Image.fromarray(out).convert("RGB")
        return pil
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
    # final resizing to max width for consistent downstream OCR
    max_w = 1800
    if img.width > max_w:
        ratio = max_w / img.width
        new_h = int(img.height * ratio)
        img = img.resize((max_w, new_h), Image.LANCZOS)
    return img

# ---------- High-level processing ----------

def process_single_object(bucket_object_path: str, batch_id: str) -> List[dict]:
    """
    Download object, convert to images (if PDF), run enhancement,
    upload enhanced images under enhanced/<batch_id>/<original_filename>_pageX.png
    Returns list of dicts with enhanced object paths and metadata.
    """
    logger.info(f"Processing {bucket_object_path} for batch {batch_id}")
    data = download_object(bucket_object_path)
    # detect if PDF by magic or path
    if bucket_object_path.lower().endswith(".pdf"):
        images = pdf_bytes_to_images(data)
    else:
        # treat as image bytes
        pil = Image.open(io.BytesIO(data)).convert("RGB")
        images = [pil]

    results = []
    # derive base filename
    _, object_name = bucket_object_path.split("/", 1)
    base_filename = object_name.split("/")[-1]

    for i, img in enumerate(images, start=1):
        enhanced = enhance_image_pipeline(img)
        buf = io.BytesIO()
        enhanced.save(buf, format="PNG", optimize=True)
        buf_bytes = buf.getvalue()
        # upload path
        bucket = settings.MINIO_BUCKET
        enhanced_object = f"enhanced/{batch_id}/{i:03d}_{base_filename}.png"
        uploaded = upload_bytes(bucket, enhanced_object, buf_bytes, content_type="image/png")
        results.append({
            "original": bucket_object_path,
            "enhanced": uploaded,
            "page": i,
            "size_bytes": len(buf_bytes)
        })
    return results
