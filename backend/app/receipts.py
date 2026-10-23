"""Local OCR and deterministic receipt parsing/calculation."""
from __future__ import annotations
import io, os, re
from decimal import Decimal
from sqlalchemy import select
from app.models.domain import EmissionFactor
from app.ocr.base import OCRLine
from app.services.grocery_normalization import match_product, normalize_unit
from app.services.receipt_table_parser import (detect_header, extract_package_size, group_rows,
    header_field_order, mapped_cells, numeric_tokens, parse_decimal_token)

def validate_image(data: bytes, content_type: str | None):
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ValueError("IMAGE_DECODER_UNAVAILABLE") from exc
    if not data: raise ValueError("EMPTY_IMAGE")
    if len(data) > int(os.getenv("RECEIPT_MAX_UPLOAD_BYTES", str(10*1024*1024))): raise ValueError("IMAGE_TOO_LARGE")
    if data.startswith(b"\xff\xd8\xff"): fmt="JPEG"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"): fmt="PNG"
    elif data[:4]==b"RIFF" and data[8:12]==b"WEBP": fmt="WEBP"
    else: raise ValueError("UNSUPPORTED_IMAGE")
    expected={"JPEG":"image/jpeg","PNG":"image/png","WEBP":"image/webp"}[fmt]
    if content_type and content_type not in (expected,"application/octet-stream"): raise ValueError("IMAGE_CONTENT_MISMATCH")
    try:
        im=Image.open(io.BytesIO(data))
        if im.width*im.height>25_000_000: raise ValueError("IMAGE_TOO_LARGE")
        im.verify(); im=ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        return fmt, im
    except ValueError: raise
    except Exception as exc: raise ValueError("INVALID_IMAGE") from exc

def preprocess_image(image):
    """Apply conservative contrast and size adjustments without losing fine print."""
    from PIL import ImageOps
    image=ImageOps.autocontrast(image.convert("RGB"),cutoff=0.5)
    max_edge=2600
    if max(image.size)>max_edge:
        scale=max_edge/max(image.size)
        image=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))))
    return image

TOTAL = re.compile(r"\b(sub.?total|grand total|total|gst|cgst|sgst|igst|tax|discount|cash|card|change|payment|round.?off|savings|loyalty|hsn)\b", re.I)
QTY = re.compile(r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>kilograms?|kgs?|kg|grams?|gms?|gm|g|litres?|liters?|ltr|l|millilitres?|milliliters?|ml|pieces?|pcs?|pc|packets?|pkt|packs?|pouches?|bottles?|boxes?|tins?|bags?|bunches|dozen)\b", re.I)
AMOUNT = re.compile(r"(?:₹|\bRs\.?|\bINR)?\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*$", re.I)
MONEY_TOKEN = re.compile(r"(?:₹|\bRs\.?|\bINR)?\s*(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?", re.I)
DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
CARD_NUMBER = re.compile(r"(?<!\d)(?:\d[ -]?){12,19}(?!\d)")

def redact_sensitive_text(text: str) -> str:
    """Do not persist receipt payment-card numbers in OCR text."""
    return CARD_NUMBER.sub("[REDACTED CARD NUMBER]", text)

def parse_date(text: str):
    """Accept common printed dates; reject ambiguous/invalid dates rather than guessing."""
    from datetime import date
    match = DATE.search(text)
    if not match: return None
    a, b, year = (int(part) for part in match.groups())
    if year < 100: year += 2000
    # Indian retail convention is DD/MM/YYYY. If both first fields are <= 12, retain
    # the conventional order but mark ambiguity in the caller's warnings.
    try: return date(year, b, a)
    except ValueError: return None

def parse_receipt(lines: list[OCRLine]):
    raw, items, total = parse_lines(lines)
    header = {"store_name": None, "store_address": None, "purchase_date": None, "invoice_number": None,
              "gstin": None, "subtotal": None, "discount_total": None, "tax_total": None, "total_amount": total,
              "currency": "INR" if re.search(r"₹|\bRs\.?|\bINR\b", raw, re.I) else None,
              "warnings": [], "reconciliation_warning": None}
    for idx, text in enumerate(raw.splitlines()):
        if header["purchase_date"] is None:
            parsed_date = parse_date(text)
            if parsed_date:
                header["purchase_date"] = parsed_date
                if DATE.search(text).group(1) and int(DATE.search(text).group(1)) <= 12 and int(DATE.search(text).group(2)) <= 12:
                    header["warnings"].append("Purchase date uses an ambiguous numeric format; confirm it.")
        gstin = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", text, re.I)
        if gstin: header["gstin"] = gstin.group(0).upper()
        invoice = re.search(r"(?:invoice|bill|receipt)\s*(?:no|number|#)?\s*[:.-]?\s*([A-Z0-9/-]{3,})", text, re.I)
        if invoice: header["invoice_number"] = invoice.group(1)
        amount_match = AMOUNT.search(text)
        amount = Decimal(amount_match.group(1).replace(",", "")) if amount_match else None
        if amount is not None:
            if re.search(r"\bsub.?total\b", text, re.I): header["subtotal"] = amount
            elif re.search(r"\bdiscount\b", text, re.I): header["discount_total"] = abs(amount)
            elif re.search(r"\b(gst|cgst|sgst|igst|tax)\b", text, re.I): header["tax_total"] = (header["tax_total"] or Decimal("0")) + amount
    header["store_name"] = next((line.strip() for line in raw.splitlines()[:4] if len(line.strip()) > 2 and not DATE.search(line) and len(numeric_tokens(line)) < 2 and not re.search(r"\b(tax invoice|invoice|gstin|phone|mob)\b", line, re.I) and not detect_header({"text": line})), None)
    if header["subtotal"] is not None:
        identifiable = sum((item["line_total"] or Decimal("0") for item in items), Decimal("0"))
        if abs(identifiable - header["subtotal"]) > Decimal("1.00"):
            header["reconciliation_warning"] = "Identifiable item totals differ from printed subtotal by more than ₹1.00; review taxes, discounts, and omitted charges."
    return {"header": header, "items": items, "raw_ocr_text": raw}

def parse_lines(lines: list[OCRLine]):
    raw=[]; items=[]; total=None; rows=group_rows(lines); header_row=None; headers=None
    for row in rows:
        text=row["text"].strip()
        if not text: continue
        raw.append(text)
        found=detect_header(row)
        if found:
            header_row=row; headers=found
            continue
        if re.search(r"\b(grand\s+total|net\s+amount|amount\s+due|bill\s+total)\b",text,re.I):
            vals=numeric_tokens(text)
            if vals: total=vals[-1][1]
            continue
        if re.search(r"\b(sub.?total|gst|cgst|sgst|igst|tax|discount|cash|card|change|payment|round.?off|savings|loyalty|hsn|thank\s+you)\b",text,re.I): continue
        if DATE.search(text) or re.search(r"\b(invoice|bill\s+no|receipt\s+no|gstin)\b",text,re.I): continue

        cells=mapped_cells(row,header_row,headers) if header_row and headers else None
        if not cells and not numeric_tokens(text): continue
        package_size=None; package_unit=None; unit_inferred=False
        description=(cells or {}).get("description", "") if cells else ""
        mrp=price_value=quantity=None; quantity_unit=None; unit_price=None; line_total=None
        semantics="UNKNOWN"; parse_confidence=.55; warnings=[]
        if cells:
            description=description or text
            mrp=parse_decimal_token((cells.get("mrp") or "").replace("₹", "").replace("Rs", "").strip())
            qty_text=cells.get("quantity", "")
            qmatch=QTY.search(qty_text)
            if qmatch:
                quantity=Decimal(qmatch.group("qty").replace(",", ".")); quantity_unit=normalize_unit(qmatch.group("unit"))
            else:
                qvals=numeric_tokens(qty_text)
                if qvals: quantity=qvals[0][1]
            value_text=cells.get("unit_price") or cells.get("line_amount") or ""
            value=parse_decimal_token(value_text.replace("₹", "").replace("Rs", "").strip())
            if value is not None:
                price_value=value
                if headers.get("line_amount") and not headers.get("unit_price"):
                    semantics="LINE_AMOUNT"; line_total=value
                elif headers.get("unit_price"):
                    semantics="UNIT_PRICE" if re.search(r"\b(rate|unit\s+price|selling\s+price|price\s+per\s+unit)\b",text,re.I) else "UNKNOWN"
                    unit_price=value if semantics=="UNIT_PRICE" else None
                parse_confidence=.9
        else:
            # Text fallback: remove a recognized package-size token, then interpret
            # the remaining numeric columns using header order and exact decimals.
            description= text
            description, package_size, package_unit=extract_package_size(description)
            tokens=numeric_tokens(description)
            if headers and headers.get("mrp") and headers.get("quantity") and (headers.get("unit_price") or headers.get("line_amount")) and len(tokens)>=3:
                vals=tokens[-3:]
                mrp,quantity,price_value=(v[1] for v in vals)
                description=description[:vals[0][2]].strip(" |:-")
                semantics="UNKNOWN" if headers.get("unit_price") else "LINE_AMOUNT"
                if semantics=="LINE_AMOUNT": line_total=price_value
                elif semantics=="UNIT_PRICE": unit_price=price_value
                if quantity is not None and quantity < 1 and any(k in description.casefold() for k in ("orange","cucumber","ginger","chill","chilli","vegetable","fruit")):
                    quantity_unit="kg"; unit_inferred=True; warnings.append("kg quantity unit inferred for a likely weighed produce item; confirm.")
                elif quantity is not None:
                    quantity_unit="pack" if package_unit else None; unit_inferred=bool(package_unit)
                parse_confidence=.82
            elif headers and headers.get("quantity") and (headers.get("line_amount") or headers.get("unit_price")):
                field_order=header_field_order(header_row)
                numeric_fields=[field for field in field_order if field in ("mrp","quantity","unit_price","line_amount")]
                if "quantity" in numeric_fields and len(tokens)>=len(numeric_fields):
                    values=tokens[-len(numeric_fields):]
                    description=description[:values[0][2]].strip(" |:-")
                    parsed_fields={field: value[1] for field,value in zip(numeric_fields,values)}
                    quantity=parsed_fields.get("quantity")
                    unit_price=parsed_fields.get("unit_price")
                    line_total=parsed_fields.get("line_amount")
                    mrp=parsed_fields.get("mrp")
                    price_value=line_total if line_total is not None else unit_price
                    semantics="LINE_AMOUNT" if line_total is not None else "UNKNOWN"
                    if quantity is not None:
                        quantity_unit="pack" if package_unit else None
                        unit_inferred=bool(package_unit)
                    parse_confidence=.82
                elif package_size is not None and "mrp" not in numeric_fields and "quantity" in numeric_fields and len(tokens)==len(numeric_fields)-1:
                    # A visible measure such as "2 kg" can itself fill the quantity
                    # column when OCR keeps the unit attached to the number.
                    quantity=package_size
                    quantity_unit=package_unit
                    remaining_fields=[field for field in numeric_fields if field!="quantity"]
                    values=tokens[-len(remaining_fields):]
                    description=description[:values[0][2]].strip(" |:-") if values else description
                    parsed_fields={field: value[1] for field,value in zip(remaining_fields,values)}
                    unit_price=parsed_fields.get("unit_price")
                    line_total=parsed_fields.get("line_amount")
                    mrp=parsed_fields.get("mrp")
                    price_value=line_total if line_total is not None else unit_price
                    semantics="LINE_AMOUNT" if line_total is not None else "UNKNOWN"
                    parse_confidence=.82
            else:
                package_size=None; package_unit=None; unit_inferred=False
                q=QTY.search(text)
                labelled_qty=re.search(r"\b(?:qty|quantity)\s*[:=]?\s*(?P<qty>\d+(?:[.,]\d+)?)\b",text,re.I)
                if not q and labelled_qty: q=labelled_qty
                if q:
                    quantity=Decimal(q.group("qty").replace(",", ".")); quantity_unit=normalize_unit(q.groupdict().get("unit")) if q.groupdict().get("unit") else None
                    description=text[:q.start()].strip(" |:-")
                    description=re.sub(r"\b(?:qty|quantity)\s*[:=]?\s*", "", description, flags=re.I).strip()
                    values=numeric_tokens(text[q.end():])
                    multi=re.search(r"(\d+(?:[.,]\d+)?)\s*[xX×]\s*"+re.escape(q.group("qty")),text[:q.end()],re.I) if q.groupdict().get("unit") else None
                    if multi:
                        package_size=quantity; package_unit=quantity_unit; quantity*=Decimal(multi.group(1).replace(",",".")); description=text[:multi.start()].strip(" |:-")
                    if len(values)>=2: unit_price=values[-2][1]
                    if values: price_value=values[-1][1]
                    if re.search(r"\b(amount|amt|line\s+total|item\s+total)\b",text,re.I) and price_value is not None:
                        semantics="LINE_AMOUNT"; line_total=price_value
                    elif unit_price is not None or re.search(r"\b(rate|unit\s+price)\b",text,re.I):
                        semantics="UNIT_PRICE"; unit_price=unit_price or price_value
                        if len(values)>=2: line_total=values[-1][1]
                    elif price_value is not None:
                        semantics="LINE_AMOUNT"; line_total=price_value
                else:
                    description=text; package_size=None; package_unit=None; unit_inferred=False
                    vals=numeric_tokens(text)
                    if vals and re.search(r"\d+\.\d{2}",text):
                        price_value=vals[-1][1]; line_total=price_value; semantics="LINE_AMOUNT"
                        description=text[:vals[-1][2]].strip(" |:-")
        if cells:
            description, package_size, package_unit=extract_package_size(description)
            unit_inferred=False
            if quantity is not None and quantity_unit is None:
                if package_unit and quantity==1: quantity_unit="pack"; unit_inferred=True
                elif quantity < 1 and any(k in description.casefold() for k in ("orange","cucumber","ginger","chill","chilli")):
                    quantity_unit="kg"; unit_inferred=True; warnings.append("kg quantity unit inferred for a likely weighed produce item; confirm.")
        description=re.sub(r"\b(?:qty|quantity|mrp|price|amount|amt|rate)\b", "", description, flags=re.I)
        description=re.sub(r"\s+", " ", description).strip(" |:-")
        if len(description)<2: continue
        match=match_product(description)
        suggested, suggested_method=categorize_candidate(description)
        if match["category"] is None and suggested: match={**match,"category":None,"method":suggested_method,"confidence":.78,"needs_confirmation":True}
        if semantics=="UNKNOWN": warnings.append("Price column meaning is ambiguous; line total was not inferred.")
        row_metadata={"mrp":str(mrp) if mrp is not None else None,"price_column_value":str(price_value) if price_value is not None else None,"price_column_semantics":semantics,"suggested_category":suggested,"package_size":str(package_size) if package_size is not None else None,"package_size_unit":package_unit,"quantity_unit_inferred":unit_inferred,"warnings":warnings}
        items.append({"raw_text":text,"name":description,"normalized_name":match["normalized_name"],"category":match["category"],"suggested_category":suggested,"match_method":match["method"] or suggested_method,"match_confidence":match["confidence"],"needs_confirmation":match["needs_confirmation"],"quantity":quantity,"unit":quantity_unit,"package_size":package_size,"package_size_unit":package_unit,"mrp":mrp,"price_column_value":price_value,"price_column_semantics":semantics,"unit_inferred":unit_inferred,"unit_price":unit_price,"line_total":line_total,"confidence":row["confidence"],"parsing_confidence":parse_confidence,"warnings":warnings,"metadata":row_metadata})
    return "\n".join(raw),items,total


def categorize_candidate(description: str):
    """Small reviewed alias set; non-food results remain suggestions, not factors."""
    text=re.sub(r"\b\d+(?:\.\d+)?\s*(?:kg|g|gm|ml|l)\b", "", description.casefold())
    rules=[(r"\b(appy|juice)\b","beverages.juice"),(r"\b(raw\s*rice|rice)\b","food.rice"),
           (r"\borange\b","food.fruits.citrus"),(r"\bcucumber\b","food.vegetables"),
           (r"\bginger\b","food.vegetables"),(r"\bgreen\s+chill?y\b","food.vegetables"),
           (r"\bsugar\b","food.sugar_sweeteners"),(r"\b(milk|cow\s+milk)\b","food.dairy"),
           (r"\b(tide|detergent)\b","household.laundry_detergent"),
           (r"\b(pepsodent|toothpaste)\b","personal_care.toothpaste")]
    for pattern, category in rules:
        if re.search(pattern,text): return category,"REVIEWED_CATEGORY_ALIAS"
    return None,None

def calculate_item(session, item):
    item.emissions_kg_co2e=None; item.matched_factor_id=None; item.calculation_details={}
    if not item.food_category: item.emissions_status="NEEDS_REVIEW"; return
    if item.quantity is None or item.quantity_unit not in ("kg","g"): item.emissions_status="QUANTITY_UNAVAILABLE"; return
    key="food_"+item.food_category.lower().replace(" ","_")+"_kg"
    factor=session.scalar(select(EmissionFactor).where(EmissionFactor.factor_key==key,EmissionFactor.geography_code=="GLOBAL",EmissionFactor.status=="APPROVED",EmissionFactor.gas=="CO2E",EmissionFactor.activity_unit=="kg"))
    if not factor or factor.value_kg_co2e_per_unit is None: item.emissions_status="FACTOR_UNAVAILABLE"; return
    mass=Decimal(item.quantity)/Decimal(1000) if item.quantity_unit=="g" else Decimal(item.quantity)
    item.emissions_kg_co2e=(mass*factor.value_kg_co2e_per_unit).quantize(Decimal("0.000001")); item.matched_factor_id=factor.id
    item.emissions_status="CALCULATED"
    item.calculation_details={"mass_kg":str(mass),"factor":str(factor.value_kg_co2e_per_unit),"factor_unit":"kgCO2e/kg","factor_id":str(factor.id),"factor_source":factor.source_name,"factor_url":factor.source_url,"limitation":"Global category-average lifecycle proxy; not India- or product-specific."}
