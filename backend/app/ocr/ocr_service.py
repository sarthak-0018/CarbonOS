"""Process-wide provider registry; model weights load on first recognition."""
from app.ocr.base import OCRLine, OCRProvider
from app.ocr.paddle_provider import PaddleProvider

_provider: OCRProvider | None = None


def get_ocr_provider() -> OCRProvider:
    global _provider
    if _provider is None:
        _provider = PaddleProvider()
    return _provider


def recognize_receipt(image_path: str) -> list[OCRLine]:
    return get_ocr_provider().recognize(image_path)
