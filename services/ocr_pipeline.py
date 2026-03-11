import logging
import os
from pathlib import Path

import torch
import torchvision.transforms as T
from PIL import Image
from pdf2image import convert_from_path
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)

_model = None
_tokenizer = None

OCR_PROMPT = "Trích xuất toàn bộ văn bản trong ảnh"

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

_IMG_TRANSFORM = T.Compose([
    T.Lambda(lambda img: img.convert("RGB")),
    T.Resize((448, 448), interpolation=InterpolationMode.BICUBIC),
    T.ToTensor(),
    T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])


def _resolve_device() -> str:
    requested = os.getenv("OCR_DEVICE", "cpu").lower()
    if requested == "cuda" and not torch.cuda.is_available():
        logger.warning("OCR_DEVICE=cuda but CUDA unavailable — falling back to cpu")
        return "cpu"
    return requested


def _load_model():
    global _model, _tokenizer
    if _model is None:
        model_name = os.getenv("OCR_MODEL", "5CD-AI/Vintern-1B-v3_5")
        device = _resolve_device()
        logger.info("Loading OCR model %s on %s", model_name, device)
        _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        _model = AutoModel.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            trust_remote_code=True,
        ).to(device).eval()
        logger.info("OCR model loaded.")
    return _model, _tokenizer


def _run_inference(image: Image.Image, model, tokenizer) -> str:
    """Run Vintern/InternVL2 inference on a single PIL image.

    Uses model.chat() — the standard InternVL2 inference API.
    The image is pre-processed with the InternVL-specific transform pipeline.
    """
    device = next(model.parameters()).device
    pixel_values = _IMG_TRANSFORM(image).unsqueeze(0).to(
        device=device,
        dtype=next(model.parameters()).dtype,
    )
    generation_config = {"max_new_tokens": 1024, "do_sample": False}
    response = model.chat(tokenizer, pixel_values, OCR_PROMPT, generation_config)
    return response.strip() if isinstance(response, str) else ""


def extract_text(file_path: str) -> list[str]:
    """Extract text from a PDF or image file using Vintern-1B OCR.

    - PDF: each page is converted to an image and passed through the VLM.
    - PNG/JPG: treated as a single-page document.
    - Failed pages are logged and skipped; remaining pages are returned.

    Returns:
        List of per-page text strings (empty pages omitted).
    """
    path = Path(file_path)
    model, tokenizer = _load_model()

    if path.suffix.lower() == ".pdf":
        try:
            images = convert_from_path(str(path))
        except Exception as exc:
            logger.error("pdf2image failed for %s: %s", file_path, exc)
            return []
    elif path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        try:
            images = [Image.open(str(path)).convert("RGB")]
        except Exception as exc:
            logger.error("Image open failed for %s: %s", file_path, exc)
            return []
    else:
        logger.warning("Unsupported file type for OCR: %s", path.suffix)
        return []

    results = []
    for page_num, image in enumerate(images, start=1):
        try:
            text = _run_inference(image, model, tokenizer)
            if text:
                results.append(text)
        except Exception as exc:
            logger.warning("OCR failed on page %d of %s: %s", page_num, file_path, exc)
            continue

    return results
