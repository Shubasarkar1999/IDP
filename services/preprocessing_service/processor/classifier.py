import torch
from transformers import AutoImageProcessor, AutoModelForImageClassification
from PIL import Image
from io import BytesIO
import torchvision.transforms as T

# ✅ Import your MinIO helper
from services.preprocessing_service.minio_client import download_object

MODEL_NAME = "google/mobilenet_v2_1.0_224"  # lightweight fallback
processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
model = AutoModelForImageClassification.from_pretrained(MODEL_NAME)

LABELS = ["aadhaar", "pan", "voter_id", "driving_license", "photo"]

def classify_document(image_path: str):
    """
    Classify an image from MinIO or local file.
    Supports both local paths and MinIO object paths.
    """
    try:
        # --- Detect if the image path is a MinIO object path ---
        if image_path.startswith("documents/"):
            print(f"[INFO] Downloading image from MinIO: {image_path}")
            image_bytes = download_object(image_path)
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        else:
            # Local file (for testing/debug)
            image = Image.open(image_path).convert("RGB")

        # --- Preprocess & Predict ---
        inputs = processor(images=image, return_tensors="pt")

        with torch.no_grad():
            logits = model(**inputs).logits
            pred = torch.argmax(logits, dim=1).item()
            confidence = torch.softmax(logits, dim=1)[0][pred].item()

        label = LABELS[pred % len(LABELS)]
        print(f"[INFO] Classified as {label} ({confidence:.2f})")

        return label, round(confidence, 3)

    except Exception as e:
        print(f"[ERROR] Classification failed for {image_path}: {e}")
        raise
