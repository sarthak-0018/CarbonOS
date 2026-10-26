import json

import httpx
import pytest

from app.ocr.base import OCRLine
from app.services.ollama_receipt_extractor import Extraction, _validated_output, extract_items, ollama_health


def test_qwen_extraction_sends_layout_and_validates_strict_json(monkeypatch):
    seen = {}
    real_client = httpx.Client
    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": json.dumps({"items": [{
            "item_name": "Rice", "quantity": 2, "unit": "kg", "price": 60,
            "total_price": 120, "source_line_numbers": [0, 1]
        }]})}})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))

    result = extract_items([
        OCRLine("ITEM QTY RATE AMOUNT", .99, [[0, 0], [200, 0], [200, 20], [0, 20]]),
        OCRLine("Rice 2 60.00 120.00", .95, [[0, 25], [200, 25], [200, 45], [0, 45]]),
    ])

    assert isinstance(result, Extraction)
    assert result.items[0].price == 60
    assert "bounds" in seen["messages"][1]["content"]
    assert seen["format"]["properties"]["items"]
    assert seen["think"] is False
    assert seen["keep_alive"] == "10m"
    assert seen["options"]["temperature"] == 0


def test_rejects_additional_fields_and_missing_source_evidence():
    with pytest.raises(Exception):
        Extraction.model_validate({"items": [{"item_name": "Rice", "quantity": 1,
            "unit": "kg", "price": 10, "source_line_numbers": [0], "merchant": "Shop"}]})


def test_normalizes_safe_decimal_and_unit_variants_before_strict_validation():
    result = _validated_output(json.dumps({"items": [{
        "item_name": "Rice", "quantity": "2.000", "unit": "KG", "price": "60.00",
        "total_price": 120, "source_line_numbers": [1]
    }]}))
    assert result.items[0].quantity.as_tuple().digits == (2, 0, 0, 0)
    assert result.items[0].unit == "kg"
    assert result.items[0].price.as_tuple().digits == (6, 0, 0, 0)


def test_unknown_unit_becomes_null_and_does_not_guess():
    result = _validated_output(json.dumps({"items": [{
        "item_name": "Unknown item", "quantity": 2, "unit": "crate", "price": None,
        "total_price": None, "source_line_numbers": [0]
    }]}))
    assert result.items[0].unit is None


def test_ollama_health_reports_unavailable_model(monkeypatch):
    request = httpx.Request("GET", "http://localhost:11434/api/tags")
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: httpx.Response(200, json={"models": []}, request=request))
    result = ollama_health()
    assert result["status"] == "model_not_pulled"
    assert result["timeout_seconds"] == 600
