"""OCR-first receipt extraction using a locally hosted Ollama model."""
from __future__ import annotations

import os
import json
import re
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ExtractedItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    item_name: str = Field(min_length=1, max_length=240)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=4)
    unit: Literal["kg", "g", "l", "ml", "each", "piece", "pack", "packet", "bottle", "box", "bag", "pouch", "tin", "bunch", "dozen"] | None = None
    package_size: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=4)
    package_size_unit: Literal["kg", "g", "l", "ml"] | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    total_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    source_line_numbers: list[int] = Field(min_length=1)


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    items: list[ExtractedItem]


def _ocr_payload(lines):
    """Keep coordinates and confidence through row construction and model selection."""
    payload = []
    for index, line in enumerate(lines):
        box = line.box or []
        ys = [float(point[1]) for point in box]
        xs = [float(point[0]) for point in box]
        payload.append({
            "line": index, "text": line.text,
            "confidence": line.confidence,
            "bounds": [min(xs), min(ys), max(xs), max(ys)] if xs and ys else None,
        })
    return payload


_UNIT_ALIASES = {
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "l": "l", "ltr": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l",
    "ml": "ml", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml",
    "each": "each", "piece": "piece", "pieces": "piece", "pc": "piece", "pcs": "piece",
    "pack": "pack", "packs": "pack", "packet": "packet", "packets": "packet",
    "bottle": "bottle", "bottles": "bottle", "box": "box", "boxes": "box",
    "bag": "bag", "bags": "bag", "pouch": "pouch", "pouches": "pouch",
    "tin": "tin", "tins": "tin", "bunch": "bunch", "bunches": "bunch", "dozen": "dozen",
}


def _validated_output(content: str) -> Extraction:
    """Normalize safe JSON scalar variants, then enforce the strict Pydantic schema."""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    # Some older Ollama/model combinations wrap valid JSON despite schema mode.
    if not content.startswith("{"):
        start, end = content.find("{"), content.rfind("}")
        if start >= 0 and end > start:
            content = content[start:end + 1]
    data = json.loads(content)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("items must be an array")
    for row in data["items"]:
        if not isinstance(row, dict):
            continue
        unit = row.get("unit")
        if isinstance(unit, str):
            canonical = _UNIT_ALIASES.get(unit.strip().casefold())
            row["unit"] = canonical  # Unknown strings remain null; never guess a unit.
        package_unit = row.get("package_size_unit")
        if isinstance(package_unit, str):
            canonical_package_unit = _UNIT_ALIASES.get(package_unit.strip().casefold())
            row["package_size_unit"] = canonical_package_unit if canonical_package_unit in {"kg", "g", "l", "ml"} else None
        for field in ("quantity", "package_size", "price", "total_price"):
            value = row.get(field)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                try:
                    row[field] = Decimal(str(value).strip())
                except Exception as exc:
                    raise ValueError(f"{field} is not a decimal") from exc
    return Extraction.model_validate(data)


def extract_items(lines: list) -> Extraction:
    """Extract purchased rows only; fail closed on unavailable or invalid local inference."""
    if not lines or not any(line.text.strip() for line in lines):
        raise ValueError("OCR_EMPTY")
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
    # Keep the Ollama schema to the portable JSON Schema subset. Pydantic's
    # Decimal validation schema contains regex/string unions some Ollama builds
    # reject; runtime validation below still uses strict Decimal-safe Pydantic.
    schema = {
        "type": "object", "additionalProperties": False, "required": ["items"],
        "properties": {"items": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["item_name", "quantity", "unit", "package_size", "package_size_unit", "price", "total_price", "source_line_numbers"],
            "properties": {
                "item_name": {"type": "string"},
                "quantity": {"type": ["number", "null"]},
                "unit": {"type": ["string", "null"]},
                "package_size": {"type": ["number", "null"]},
                "package_size_unit": {"type": ["string", "null"], "enum": ["kg", "g", "l", "ml", None]},
                "price": {"type": ["number", "null"]},
                "total_price": {"type": ["number", "null"]},
                "source_line_numbers": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
            },
        }}}
    }
    prompt = """Extract purchased grocery/product line items from this OCR with layout coordinates.
Use only values explicitly supported by OCR. Never infer missing purchase quantity, unit or price.
Ignore store/customer details, tax, subtotal, totals, payment and footer rows.
For MRP/RATE/AMOUNT columns, price is RATE (selling price per purchased unit), never MRP;
total_price is printed AMOUNT when identified. For QTY/AMOUNT without RATE, price is null.
Keep purchase quantity/unit separate from printed net content/package_size/package_size_unit.
For 2 packs of Almond 200 g, return quantity=2, unit=pack, package_size=200,
package_size_unit=g. Never replace the pack count with 400 g. Extract printed juice/drink
net content as ml or l, but never infer a volume unit merely from the product category.
If no purchased count is printed, leave quantity null rather than assuming one pack.
For genuinely ambiguous price columns, price must be null. Return exact zero-based source_line_numbers
using each OCR entry's line field; cite every line used for the item and no nonexistent lines.
Return only the required JSON schema."""
    try:
        ocr_input = str(_ocr_payload(lines))
        validation_error = None
        with httpx.Client(timeout=timeout) as client:
            for attempt in range(2):
                retry_hint = "" if attempt == 0 else (
                    "Previous output was invalid. Return every required key for every item, use null for unknown values, "
                    "canonical units only, and exact zero-based OCR line indices. Return valid JSON only."
                )
                response = client.post(f"{base}/api/chat", json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": prompt + " " + retry_hint},
                        {"role": "user", "content": ocr_input},
                    ],
                    "stream": False,
                    "format": schema,
                    "think": False,
                    "keep_alive": "10m",
                    "options": {"temperature": 0, "num_predict": 4096},
                })
                response.raise_for_status()
                message = response.json().get("message", {}).get("content", "")
                try:
                    return _validated_output(message)
                except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                    validation_error = exc
        if isinstance(validation_error, ValidationError):
            fields = ",".join(".".join(str(part) for part in e["loc"]) + ":" + e["type"] for e in validation_error.errors()[:6])
            raise RuntimeError("OLLAMA_INVALID_OUTPUT:" + fields) from validation_error
        raise RuntimeError("OLLAMA_INVALID_OUTPUT:json") from validation_error
    except httpx.TimeoutException as exc:
        raise RuntimeError("OLLAMA_TIMEOUT") from exc
    except httpx.ConnectError as exc:
        raise RuntimeError("OLLAMA_UNAVAILABLE") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"OLLAMA_HTTP_{exc.response.status_code}") from exc
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise RuntimeError("OLLAMA_RESPONSE_INVALID") from exc


def ollama_health() -> dict:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
    try:
        response = httpx.get(f"{base}/api/tags", timeout=3)
        response.raise_for_status()
        names = {entry.get("name") for entry in response.json().get("models", [])}
        available = model in names or f"{model}:latest" in names
        return {"provider": "ollama-local", "model": model, "timeout_seconds": timeout, "available": available,
                "status": "ready" if available else "model_not_pulled"}
    except httpx.HTTPError:
        return {"provider": "ollama-local", "model": model, "timeout_seconds": timeout, "available": False, "status": "unavailable"}
