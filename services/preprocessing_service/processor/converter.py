import fitz  # PyMuPDF
import tempfile

def pdf_to_images(pdf_path):
    """
    Converts each page of a PDF into images and returns their local file paths.
    """
    images = []
    print(f"[INFO] Converting PDF to images: {pdf_path}")
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_path = tempfile.NamedTemporaryFile(suffix=f"_page{i}.png", delete=False).name
            pix.save(img_path)
            images.append(img_path)
    print(f"[INFO] Extracted {len(images)} image(s) from {pdf_path}")
    return images
