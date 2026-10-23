"""PaddleOCR CPU provider with a local Tesseract fallback."""
import os

from app.ocr.base import OCRLine


class PaddleProvider:
    _engine = None
    _active_version = "paddleocr-3.3.2-en"
    _paddle_error = None

    @property
    def version(self):
        return self._active_version

    def recognize(self, image_path: str) -> list[OCRLine]:
        if self._paddle_error is None:
            try:
                if self._engine is None:
                    cache = os.getenv("PADDLE_PDX_CACHE_HOME", os.getenv("PADDLE_HOME", "/models/paddle"))
                    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", cache)
                    os.environ.setdefault("PADDLE_HOME", cache)
                    from paddleocr import PaddleOCR
                    language = os.getenv("OCR_LANGUAGE", "en").strip().lower()
                    if language not in {"en", "hi", "mr"}:
                        raise RuntimeError("OCR_LANGUAGE must be one of en, hi, or mr")
                    self._engine = PaddleOCR(
                        lang=language, device="cpu", use_doc_orientation_classify=False,
                        use_doc_unwarping=False, use_textline_orientation=False,
                    )
                    self._active_version = f"paddleocr-3.3.2-{language}"
                output = []
                for result in self._engine.predict(image_path):
                    data = result.json if hasattr(result, "json") else result
                    if callable(data):
                        data = data()
                    data = data.get("res", data) if isinstance(data, dict) else {}
                    texts, scores = data.get("rec_texts", []), data.get("rec_scores", [])
                    boxes = data.get("rec_polys", data.get("dt_polys", []))
                    for i, text in enumerate(texts):
                        box = boxes[i].tolist() if i < len(boxes) and hasattr(boxes[i], "tolist") else boxes[i] if i < len(boxes) else []
                        output.append(OCRLine(str(text), float(scores[i]) if i < len(scores) else None, box))
                if output:
                    return sorted(output, key=lambda line: (min((point[1] for point in line.box), default=0), min((point[0] for point in line.box), default=0)))
                self._paddle_error = "PaddleOCR returned no text lines"
            except Exception as exc:
                self._paddle_error = f"{type(exc).__name__}: {exc}"

        try:
            import pytesseract
            from pytesseract import Output
            from PIL import Image
            if os.getenv("TESSERACT_CMD"):
                pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
            data = pytesseract.image_to_data(Image.open(image_path), lang="eng", output_type=Output.DICT, config="--psm 6")
            grouped = {}
            for i, text in enumerate(data.get("text", [])):
                text = text.strip()
                if not text:
                    continue
                try:
                    confidence = max(0.0, float(data["conf"][i]) / 100.0)
                except (ValueError, TypeError):
                    confidence = None
                x, y, w, h = (int(data[key][i]) for key in ("left", "top", "width", "height"))
                line = OCRLine(text, confidence, [[x, y], [x + w, y], [x + w, y + h], [x, y + h]])
                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                if key not in grouped:
                    grouped[key] = line
                else:
                    previous = grouped[key]
                    previous.text += " " + line.text
                    if previous.confidence is not None and line.confidence is not None:
                        previous.confidence = (previous.confidence + line.confidence) / 2
                    left, top = min(previous.box[0][0], x), min(previous.box[0][1], y)
                    right, bottom = max(previous.box[2][0], x + w), max(previous.box[2][1], y + h)
                    previous.box = [[left, top], [right, top], [right, bottom], [left, bottom]]
            if not grouped:
                raise RuntimeError("Tesseract found no text; check image quality and English language data")
            self._active_version = "tesseract-local-fallback-eng"
            return sorted(grouped.values(), key=lambda line: (line.box[0][1], line.box[0][0]))
        except Exception as exc:
            raise RuntimeError(f"PaddleOCR failed ({self._paddle_error}); local Tesseract fallback failed ({type(exc).__name__})") from exc
