# Grocery receipt scanning

The Grocery Scanner is available at `/receipts` after creating a CarbonOS profile. It accepts JPG/JPEG, PNG, and WebP images up to 10 MB. The API checks file signatures against MIME type and extension, decodes the image, applies EXIF orientation, rejects images above 25 megapixels, and stores the original under a generated UUID in controlled receipt storage. OCR input uses conservative autocontrast and downsizing; fine print is retained. The original can be viewed through the profile-scoped receipt preview endpoint.

## OCR and local extraction configuration

PaddleOCR 3.3.2 with PaddlePaddle 3.2.2 CPU is the preferred local provider. Paddle model loading is lazy and reused for the process lifetime. The Docker image uses Python 3.12 and installs local Tesseract 5 English as a real local fallback. OCR failures are persisted as `FAILED`, and the image remains available for `POST /api/receipts/{id}/process` retry. PaddleX weights are cached in the configured model volume. No receipt content is sent to a cloud OCR service.

The OCR engine retains text, coordinates, and confidence. Image preparation applies EXIF orientation, conservative contrast, sharpening, and OpenCV CLAHE; it avoids hard binarization that can erase faint decimal points. `OCR_LANGUAGE` defaults to `en`; `hi` and `mr` select PaddleOCR's Devanagari recognition model. Hindi/Marathi and English-only Tesseract fallback have not been validated against real receipts.

Qwen 3 performs local, OCR-first item extraction. Configure `OLLAMA_BASE_URL` (default in Docker: `http://host.docker.internal:11434`), `OLLAMA_MODEL` (default `qwen3:8b`) and `OLLAMA_TIMEOUT_SECONDS` (600 seconds). The API sends only OCR text and its layout coordinates to Ollama, requests schema-constrained JSON with temperature 0 and Qwen3 thinking disabled for this constrained extraction, and independently validates every field and cited OCR line. The model is kept loaded for 10 minutes after a request. The service does not fall back to a cloud provider or invent a missing price. `GET /api/receipts/ollama-health` reports whether the configured model is reachable and the effective extraction timeout. On Windows/macOS Docker Desktop, run Ollama on the host; on Linux, adjust `OLLAMA_BASE_URL` to a host-reachable address and configure Docker networking accordingly.

Example local setup (install Ollama separately from its official installer):

```powershell
ollama pull qwen3:8b
ollama serve
```

Ensure `.env` has `OLLAMA_MODEL=qwen3:8b`, then rebuild/restart the API with `docker compose up --build`. The first PaddleOCR run downloads its recognition/detection weights into the persistent `paddle_models` volume. The Docker image installs pinned PaddleOCR 3.3.2 / PaddlePaddle 3.2.2 and OpenCV headless 4.10.0.84; first-run OCR needs network access to fetch model weights. Qwen 3 JSON mode is requested via Ollama's JSON Schema format; Pydantic validation remains authoritative.

## Extracted and reviewed data

The deterministic parser remains available for receipt-level totals and debugging, and recognizes common quantity/rate/amount layouts. Qwen 3 provides the persisted item rows using strict fields and source OCR line references. Selling price is the rate when identified; printed amount stays internal. Product net content (for example 200 g or 500 ml) is stored separately from purchased count. When both pack count and printed net content are known, CarbonOS derives a total content amount (2 packs × 200 g = 400 g); it does not overwrite the purchased count. Volume amounts remain volume and are not converted to mass without a valid density. Unknown prices/units remain null. A local model failure marks the receipt `FAILED` while retaining its image for retry.

Product aliases are editable in `backend/app/data/product_aliases.json`. Exact aliases include selected English, Hindi, and Marathi names. A prefix alias match is accepted only when followed by a numeric size or unit; for example, rice flour remains distinct from rice. Unmatched products remain visible and require review. Product alias confidence is separate from OCR and parsing confidence. Package counts are not converted to mass, and price is never used as quantity. The UI allows correction of receipt totals, descriptions, quantities, units, package sizes, unit prices, line totals, and food category; users may add or remove rows.

Records are stored in the existing PostgreSQL `receipts` and `receipt_items` tables. Migrations additively extend existing data. Uploaded images are stored outside the public frontend directory. SHA-256 avoids repeated creation for an identical upload within the same profile. Processing states include `PROCESSING`, `REVIEW_REQUIRED`, `FAILED`, and `CONFIRMED`.

Use `docker compose up --build`, then apply additive schema changes with `docker compose exec api alembic upgrade head`. Check `GET /api/health` and `GET /api/receipts/ollama-health`. Run backend checks with `docker compose exec api pytest`. Synthetic and mocked fixtures do not demonstrate real-image OCR accuracy.

The existing calculation engine can produce a category-average estimate only after a supported mass quantity, selected food category, and approved factor are present. Imported global food factors are not India-specific product measurements. OCR output by itself is not a carbon footprint. Milestone 4 should connect confirmed products/categories and sufficient quantities to a reviewed factor registry, keep the factor's provenance and geography limitations visible, and calculate deterministically.

## Current limitations

- No permitted real receipt image set is checked in, so real-image OCR has not been validated and no accuracy percentage is claimed.
- The existing `/receipts` UI and workflow still require single-file upload and user review/confirmation; automatic batch acceptance and the evaluation dashboard are not implemented yet.
- Qwen 3 extraction quality has not yet been measured against a labeled receipt set. Local Qwen 3 8B may require substantial RAM/VRAM and can be slow on CPU.
- No robust Hindi/Marathi recognition evaluation has been performed.
- Store-address extraction is not yet implemented; unsupported header fields remain blank.
- The parser is deterministic and receipt-layout agnostic, but unusual column layouts may need user correction.
- Profile ID is the existing app's ownership convention, not authentication. Requests are not safe to expose on an untrusted network until account authentication is added.
- Receipt retention/deletion controls are not yet exposed.
- No barcode lookup or external product service is used.
- No emissions factors are inferred from prices or product metadata.
