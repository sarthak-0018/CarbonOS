# Grocery receipt scanning

The Grocery Scanner is available at `/receipts` after creating a CarbonOS profile. It accepts JPG/JPEG, PNG, and WebP images up to 10 MB. The API checks file signatures against MIME type and extension, decodes the image, applies EXIF orientation, rejects images above 25 megapixels, and stores the original under a generated UUID in controlled receipt storage. OCR input uses conservative autocontrast and downsizing; fine print is retained. The original can be viewed through the profile-scoped receipt preview endpoint.

## OCR configuration

PaddleOCR 3.3.2 with PaddlePaddle 3.2.2 CPU is the preferred local provider. Paddle model loading is lazy and reused for the process lifetime. The Docker image uses Python 3.12 and installs local Tesseract 5 English as a real local fallback. OCR failures are persisted as `FAILED`, and the image remains available for `POST /api/receipts/{id}/process` retry. PaddleX weights are cached in the configured model volume. No receipt content is sent to a cloud OCR service.

`OCR_LANGUAGE` defaults to `en`; `hi` and `mr` select PaddleOCR's Devanagari recognition model. The PaddleOCR language table lists Hindi and Marathi support and the Devanagari model also includes English, but CarbonOS has not validated recognition quality against real Hindi or Marathi retail receipts. The Tesseract fallback is English-only. See the [PaddleOCR multilingual model documentation](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html).

## Extracted and reviewed data

The deterministic parser preserves raw OCR text and line confidence, and extracts candidate store name, date, invoice number, GSTIN, INR currency, subtotal, discount, tax, total, and item rows. It recognizes common kg/g/l/ml/count and package terms, quantity/rate/amount layouts (including unboxed rows using the order of table headers), discounts, GST/CGST/SGST/IGST labels, and common Indian date formats. Numeric dates with day and month both at most 12 are flagged for review. Unknown values remain empty. Subtotal mismatch is a warning with a ₹1.00 tolerance; it never changes line amounts.

Product aliases are editable in `backend/app/data/product_aliases.json`. Exact aliases include selected English, Hindi, and Marathi names. A prefix alias match is accepted only when followed by a numeric size or unit; for example, rice flour remains distinct from rice. Unmatched products remain visible and require review. Product alias confidence is separate from OCR and parsing confidence. Package counts are not converted to mass, and price is never used as quantity. The UI allows correction of receipt totals, descriptions, quantities, units, package sizes, unit prices, line totals, and food category; users may add or remove rows.

Records are stored in the existing PostgreSQL `receipts` and `receipt_items` tables. Migration `20261022_0009` adds receipt header, processing, checksum, package-size, and product-match confidence fields without deleting existing rows. Uploaded images are stored outside the public frontend directory. SHA-256 avoids repeated creation for an identical upload within the same profile. Processing states include `PROCESSING`, `REVIEW_REQUIRED`, `FAILED`, and `CONFIRMED`; OCR does not confirm a receipt.

Use `docker compose up --build`, then apply the additive schema changes with `docker compose exec api alembic upgrade head`. API health is `GET /api/health`. Run backend checks with `docker compose exec api pytest`. To test manually, create a profile, open `/receipts`, upload a real printed grocery receipt, inspect it against the preview, correct at least one field, save corrections, confirm, then refresh and reopen the saved receipt from history. Synthetic parser fixtures are test data and do not demonstrate real-image OCR accuracy.

The existing calculation engine can produce a category-average estimate only after a supported mass quantity, selected food category, and approved factor are present. Imported global food factors are not India-specific product measurements. OCR output by itself is not a carbon footprint. Milestone 4 should connect confirmed products/categories and sufficient quantities to a reviewed factor registry, keep the factor's provenance and geography limitations visible, and calculate deterministically.

## Current limitations

- No permitted real receipt image set is checked in, so real-image OCR has not been validated and no accuracy percentage is claimed.
- No robust Hindi/Marathi recognition evaluation has been performed.
- Store-address extraction is not yet implemented; unsupported header fields remain blank.
- The parser is deterministic and receipt-layout agnostic, but unusual column layouts may need user correction.
- Profile ID is the existing app's ownership convention, not authentication. Requests are not safe to expose on an untrusted network until account authentication is added.
- Receipt retention/deletion controls are not yet exposed.
- No barcode lookup or external product service is used.
- No emissions factors are inferred from prices or product metadata.
