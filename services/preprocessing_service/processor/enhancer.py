import cv2
import numpy as np
import os
from skimage import exposure
import logging

logger = logging.getLogger(__name__)

def enhance_image(image_path: str) -> bytes:
    """
    Enhances the image and returns the enhanced image as bytes.
    """
    try:
        logger.info(f"[ENHANCER] Starting enhancement for: {image_path}")

        # Read the image
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        img_array = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Failed to decode image from: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # --- Deblur ---
        psf = np.ones((5, 5)) / 25
        deconvolved = cv2.filter2D(gray, -1, psf)

        # --- Contrast enhancement ---
        equalized = exposure.equalize_adapthist(deconvolved, clip_limit=0.03)
        enhanced = (equalized * 255).astype(np.uint8)

        # --- Deskew ---
        coords = np.column_stack(np.where(enhanced > 0))
        if coords.size == 0:
            raise ValueError("Empty image — cannot deskew.")
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        (h, w) = enhanced.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        deskewed = cv2.warpAffine(enhanced, M, (w, h),
                                  flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        # Encode as PNG bytes
        success, encoded_img = cv2.imencode(".png", deskewed)
        if not success:
            raise IOError("Failed to encode enhanced image")

        return encoded_img.tobytes()

    except Exception as e:
        logger.error(f"[ENHANCER] Enhancement failed for {image_path}: {e}", exc_info=True)
        raise
