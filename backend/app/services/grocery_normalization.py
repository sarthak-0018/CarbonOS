"""Conservative normalisation helpers for Indian grocery receipt text."""
from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

ALIASES_PATH = Path(__file__).resolve().parents[1] / "data" / "product_aliases.json"


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    key = re.sub(r"[.\s]", "", unit.casefold())
    return {
        "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
        "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
        "l": "l", "ltr": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l",
        "ml": "ml", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml",
        "pc": "each", "pcs": "each", "piece": "each", "pieces": "each", "unit": "each",
        "dozen": "dozen", "packet": "packet", "pkt": "packet", "pack": "pack",
        "pouch": "pouch", "bottle": "bottle", "box": "box", "tin": "tin", "bag": "bag", "bunch": "bunch",
    }.get(key, unit.strip().casefold())


def normalize_product_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("×", " x ")
    value = re.sub(r"(?<=\d)\s+(?=kg\b|gm?\b|ml\b|ltr\b)", "", value)
    value = re.sub(r"[^\w.]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def match_product(value: str) -> dict:
    """Return an evidence-backed alias match; preserve uncertainty explicitly."""
    normalized = normalize_product_text(value)
    try:
        aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        aliases = {}
    # Match whole leading/trailing tokens and retain quantity/variant words in the display name.
    for canonical, entries in aliases.items():
        for alias in entries:
            candidate = normalize_product_text(alias)
            if normalized == candidate:
                tail = ""
            elif normalized.startswith(candidate + " "):
                tail = normalized[len(candidate):].strip()
                # Permit only an explicit size/quantity suffix. "Rice flour" must not
                # collapse into rice just because the first token matches.
                if not re.match(r"^(?:\d|kg\b|g\b|gm\b|ml\b|l\b)", tail):
                    continue
            else:
                continue
            if normalized == candidate or tail:
                return {"normalized_name": normalized, "category": canonical, "method": "EXACT_ALIAS", "confidence": 0.96, "needs_confirmation": False, "evidence": alias}
    return {"normalized_name": normalized, "category": None, "method": None, "confidence": None, "needs_confirmation": True, "evidence": None}


def parse_indian_amount(text: str) -> Decimal | None:
    cleaned = text.replace("₹", " ").replace("INR", " ")
    match = re.search(r"(?i)\bRs\.?\s*([\d,]+(?:\.\d{1,2})?)|([\d,]+\.\d{2})\s*$", cleaned)
    if not match:
        return None
    value = next(group for group in match.groups() if group is not None)
    try:
        return Decimal(value.replace(",", ""))
    except Exception:
        return None
