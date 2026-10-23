"""Header-aware deterministic parsing helpers for retail receipt tables."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.ocr.base import OCRLine

NUMBER_RE = re.compile(r"(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w.])")
UNIT_RE = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)\s*(kg|k\.g\.?|kilograms?|gms?|gm|grams?|g|millilit(?:er|re)s?|ml|lit(?:er|re)s?|l)(?!\w)", re.I)
HEADER_PATTERNS = {
    "description": r"\b(item\s*name|item|product\s*name|product|description|particulars|goods|article)\b",
    "mrp": r"\b(m\.?r\.?p\.?|maximum\s+retail\s+price)\b",
    "quantity": r"\b(qty|quantity|weight|net\s+quantity)\b",
    "unit_price": r"\b(rate|unit\s+price|selling\s+price|price\s+per\s+unit|price)\b",
    "line_amount": r"\b(amount|amt|line\s+amount|line\s+total|net\s+amount|item\s+total|extended\s+price|total)\b",
}


def parse_decimal_token(token: str) -> Decimal | None:
    """Parse a complete decimal token; reject malformed Indian grouping."""
    value = token.strip().replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    if not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", value):
        return None
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None


def normalize_measure(unit: str) -> str:
    value = re.sub(r"[.\s]", "", unit.casefold())
    if value in {"kg", "kgs", "kilogram", "kilograms"}: return "kg"
    if value in {"g", "gm", "gms", "gram", "grams"}: return "g"
    if value in {"ml", "milliliter", "milliliters", "millilitre", "millilitres"}: return "ml"
    if value in {"l", "litre", "litres", "liter", "liters"}: return "l"
    return value


def extract_package_size(description: str):
    match = UNIT_RE.search(description)
    if not match: return description.strip(), None, None
    size = parse_decimal_token(match.group(1))
    cleaned = (description[:match.start()] + " " + description[match.end():]).strip(" -|·")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, size, normalize_measure(match.group(2))


def box_bounds(line: OCRLine):
    box = line.box or []
    if not box: return None
    xs = [float(p[0]) for p in box]; ys = [float(p[1]) for p in box]
    return min(xs), min(ys), max(xs), max(ys)


def group_rows(lines: list[OCRLine]):
    """Cluster OCR fragments by vertical overlap and sort cells left-to-right."""
    entries = [(line, box_bounds(line)) for line in lines if line.text.strip()]
    entries.sort(key=lambda item: ((item[1][1] + item[1][3]) / 2 if item[1] else 0,
                                  item[1][0] if item[1] else 0))
    rows = []
    for line, bounds in entries:
        cy = (bounds[1] + bounds[3]) / 2 if bounds else None
        height = bounds[3] - bounds[1] if bounds else 0
        if rows and cy is not None and rows[-1]["cy"] is not None and abs(cy - rows[-1]["cy"]) <= max(8, (height + rows[-1]["height"]) * .65):
            rows[-1]["lines"].append((line, bounds))
            ys = [(b[1]+b[3])/2 for _, b in rows[-1]["lines"] if b]
            rows[-1]["cy"] = sum(ys)/len(ys) if ys else rows[-1]["cy"]
            rows[-1]["height"] = max(rows[-1]["height"], height)
        else:
            rows.append({"cy": cy, "height": height, "lines": [(line, bounds)]})
    for row in rows:
        row["lines"].sort(key=lambda pair: pair[1][0] if pair[1] else 0)
        row["text"] = " ".join(line.text.strip() for line, _ in row["lines"])
        row["confidence"] = min((line.confidence for line, _ in row["lines"] if line.confidence is not None), default=None)
    return rows


def detect_header(row):
    text = row["text"]
    found = {key: bool(re.search(pattern, text, re.I)) for key, pattern in HEADER_PATTERNS.items()}
    # Require a description cue and at least two numeric field cues to avoid
    # mistaking product names or footer text for a table header.
    if found["description"] and sum(found[key] for key in ("mrp", "quantity", "unit_price", "line_amount")) >= 2:
        return found
    return None


def header_field_order(row):
    """Return detected table fields from left to right when OCR has no cell boxes."""
    occurrences = []
    for key, pattern in HEADER_PATTERNS.items():
        for match in re.finditer(pattern, row["text"], re.I):
            occurrences.append((match.start(), -(match.end() - match.start()), key))
    occurrences.sort()
    fields = []
    occupied_until = -1
    for start, negative_length, key in occurrences:
        end = start - negative_length
        if start >= occupied_until:
            fields.append(key)
            occupied_until = end
    return fields


def mapped_cells(row, header_row, headers):
    """Assign OCR fragments to header columns by x-centre when anchors exist."""
    anchors = {}
    for line, box in header_row["lines"]:
        if not box: continue
        for key, pattern in HEADER_PATTERNS.items():
            if re.search(pattern, line.text, re.I): anchors.setdefault(key, []).append((box[0]+box[2])/2)
    anchors = {key: sum(values)/len(values) for key, values in anchors.items()}
    if len(anchors) < 2 or max(anchors.values()) - min(anchors.values()) < 3 or not all(box for _, box in row["lines"]): return None
    cells = {key: [] for key in headers}
    for line, box in row["lines"]:
        center=(box[0]+box[2])/2
        nearest=min(anchors, key=lambda key: abs(center-anchors[key]))
        cells.setdefault(nearest, []).append(line.text.strip())
    return {key: " ".join(values).strip() for key, values in cells.items()}


def numeric_tokens(text: str):
    return [(m.group(0), parse_decimal_token(m.group(0)), m.start(), m.end()) for m in NUMBER_RE.finditer(text)]
