"""Conservative normalisation helpers for Indian grocery receipt text."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from decimal import Decimal
from pathlib import Path

ALIASES_PATH = Path(__file__).resolve().parents[1] / "data" / "product_aliases.json"
USDA_ALIASES_PATH = Path(__file__).resolve().parents[1] / "data" / "usda_food_aliases.json"
BRANDS_PATH = Path(__file__).resolve().parents[1] / "data" / "product_brands.json"


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


@lru_cache(maxsize=1)
def _product_aliases() -> tuple[tuple[str, tuple[tuple[str, str], ...], str], ...]:
    """Load curated aliases first, followed by the USDA-derived vocabulary."""
    compiled = []
    for path in (ALIASES_PATH, USDA_ALIASES_PATH):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for category, entries in document.items():
            compiled.append((category, tuple((alias, normalize_product_text(alias)) for alias in entries),
                             "EXACT_ALIAS" if path == ALIASES_PATH else "USDA_FOOD_ALIAS"))
    return tuple(compiled)


@lru_cache(maxsize=1)
def _brand_aliases() -> tuple[tuple[str, str], ...]:
    try:
        document = json.loads(BRANDS_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ()
    return tuple(sorted(
        ((normalize_product_text(alias), brand) for brand, aliases in document.items() for alias in aliases),
        key=lambda entry: len(entry[0]), reverse=True,
    ))


def _match_alias(normalized: str) -> dict | None:
    for canonical, entries, method in _product_aliases():
        for alias, candidate in entries:
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
                return {"category": canonical, "method": method,
                        "confidence": 0.96 if method == "EXACT_ALIAS" else 0.90,
                        "needs_confirmation": False, "evidence": alias}
    return None


def match_product(value: str) -> dict:
    """Return an evidence-backed alias match; preserve uncertainty explicitly."""
    normalized = normalize_product_text(value)
    direct = _match_alias(normalized)
    if direct:
        return {"normalized_name": normalized, "brand": None, **direct}

    # Only remove a brand when it is an explicit, leading, known brand alias.
    # This preserves the raw product name and prevents arbitrary prefixes being discarded.
    for brand_alias, brand in _brand_aliases():
        prefix = brand_alias + " "
        if not normalized.startswith(prefix):
            continue
        product = normalized[len(prefix):].strip()
        # Known milk product-line labels are brand descriptors, not food identities.
        product = re.sub(r"^(?:taaza|gold|slim n trim|slim|premium)\s+", "", product)
        matched = _match_alias(product)
        if matched:
            return {"normalized_name": normalized, "brand": brand,
                    "method": "BRAND_PREFIX_ALIAS", "confidence": 0.92,
                    "needs_confirmation": False, "evidence": matched["evidence"],
                    "category": matched["category"]}
        break
    return {"normalized_name": normalized, "brand": None, "category": None,
            "method": None, "confidence": None, "needs_confirmation": True, "evidence": None}


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
