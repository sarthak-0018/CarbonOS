import io

import pytest
Image = pytest.importorskip("PIL.Image", reason="Pillow is declared in backend requirements but is not installed in this local interpreter")

from app.receipts import preprocess_image, validate_image


def image_bytes(fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (240, 640), "white").save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.mark.parametrize("fmt,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_supported_image_formats_and_safe_preprocessing(fmt, mime):
    detected, image = validate_image(image_bytes(fmt), mime)
    assert detected == fmt
    processed = preprocess_image(image)
    assert processed.mode == "RGB"
    assert processed.size == (240, 640)


def test_rejects_content_mismatch_corrupt_and_empty_uploads():
    with pytest.raises(ValueError, match="IMAGE_CONTENT_MISMATCH"):
        validate_image(image_bytes("PNG"), "image/jpeg")
    with pytest.raises(ValueError, match="UNSUPPORTED_IMAGE"):
        validate_image(b"not an image", "image/png")
    with pytest.raises(ValueError, match="EMPTY_IMAGE"):
        validate_image(b"", None)


def test_rejects_oversized_upload(monkeypatch):
    monkeypatch.setenv("RECEIPT_MAX_UPLOAD_BYTES", "10")
    with pytest.raises(ValueError, match="IMAGE_TOO_LARGE"):
        validate_image(image_bytes(), "image/png")
