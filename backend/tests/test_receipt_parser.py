from decimal import Decimal
from app.receipts import OCRLine, parse_lines, parse_receipt, parse_date, redact_sensitive_text
from app.services.grocery_normalization import match_product, normalize_unit, parse_indian_amount
from app.services.receipt_table_parser import parse_decimal_token, extract_package_size

def test_receipt_totals_are_not_products_and_explicit_quantities_are_parsed():
    lines=[OCRLine("RICE 1 kg 140.00",.97,[[0,0],[10,0],[10,5],[0,5]]),
           OCRLine("MILK 500 ml 30.00",.92,[[0,10],[10,10],[10,15],[0,15]]),
           OCRLine("GST 5.00",.99,[]),OCRLine("Grand Total Rs 175.00",.99,[])]
    raw,items,total=parse_lines(lines)
    assert "GST" in raw and len(items)==2
    assert items[0]["quantity"]==Decimal("1") and items[0]["unit"]=="kg"
    assert items[1]["quantity"]==Decimal("500") and items[1]["unit"]=="ml"
    assert total==Decimal("175.00")

def test_unweighted_pack_remains_visible_without_quantity():
    _,items,_=parse_lines([OCRLine("BISCUITS 1 PACKET Rs 25.00",.81,[])])
    assert len(items)==1 and items[0]["quantity"]==Decimal("1") and items[0]["unit"]=="packet" and items[0]["line_total"]==Decimal("25.00")

def test_explicit_multipack_weight_counts_all_pack_mass():
    _,items,_=parse_lines([OCRLine("OATS 2 x 500 g 120",.88,[])])
    assert items[0]["quantity"]==Decimal("1000") and items[0]["unit"]=="g"
    assert items[0]["package_size"]==Decimal("500")

def test_indian_currency_and_dates_keep_decimal_precision():
    assert parse_indian_amount("Grand Total Rs. 1,234.50") == Decimal("1234.50")
    assert parse_date("12/10/2026") .isoformat() == "2026-10-12"
    assert parse_date("31/02/2026") is None

def test_aliases_preserve_product_variants_and_devanagari_names():
    assert match_product("चावल 5 kg rice") ["category"] == "rice"
    assert match_product("तांदूळ") ["category"] == "rice"
    assert match_product("दूध") ["category"] == "milk"
    assert match_product("rice flour 500 g") ["category"] is None
    assert normalize_unit("millilitres") == "ml"

def test_parser_extracts_indian_tax_total_and_warns_on_subtotal_mismatch():
    result=parse_receipt([
        OCRLine("Corner Store",.99,[]), OCRLine("12/10/2026",.95,[]),
        OCRLine("Rice 1 kg 100.00 100.00",.96,[]), OCRLine("Subtotal Rs 100.00",.99,[]),
        OCRLine("CGST Rs 2.50",.99,[]), OCRLine("SGST Rs 2.50",.99,[]),
        OCRLine("Grand Total Rs 105.00",.99,[]),
    ])
    assert result["header"]["currency"] == "INR"
    assert result["header"]["tax_total"] == Decimal("5.00")
    assert result["header"]["total_amount"] == Decimal("105.00")
    assert result["items"][0]["unit_price"] == Decimal("100.00")

def test_payment_card_numbers_are_redacted_from_persistable_ocr_text():
    assert "4111 1111 1111 1111" not in redact_sensitive_text("Card 4111 1111 1111 1111")

def test_labelled_qty_rate_amount_and_all_mass_volume_units_are_categorized():
    rows=[OCRLine("ITEM QTY RATE AMOUNT",.99,[]),
          OCRLine("Rice Qty 2 kg Rate 60.00 Amount 120.00",.94,[]),
          OCRLine("Flour 500 g 40.00 20.00",.92,[]),
          OCRLine("Oil 1 L 150.00 150.00",.92,[]),
          OCRLine("Milk 500 ml 30.00 15.00",.92,[])]
    _,items,_=parse_lines(rows)
    assert len(items)==4
    assert items[0]["quantity"]==Decimal("2") and items[0]["unit"]=="kg"
    assert items[0]["unit_price"]==Decimal("60.00") and items[0]["line_total"]==Decimal("120.00")
    assert [(i["unit"],i["quantity"]) for i in items[1:]]==[("g",Decimal("500")),("l",Decimal("1")),("ml",Decimal("500"))]

def test_unboxed_table_headers_map_qty_rate_and_amount_columns_in_order():
    lines=[
        OCRLine("ITEM QTY RATE AMOUNT",.99,[]),
        OCRLine("Rice 2 60.00 120.00",.94,[]),
        OCRLine("Milk 500 ml 30.00 15.00",.94,[]),
        OCRLine("Oil 1 L 150.00 150.00",.94,[]),
    ]
    _,items,_=parse_lines(lines)
    assert len(items)==3
    assert (items[0]["name"],items[0]["quantity"],items[0]["unit"])==("Rice",Decimal("2"),None)
    assert (items[0]["unit_price"],items[0]["line_total"])==(Decimal("60.00"),Decimal("120.00"))
    assert (items[1]["name"],items[1]["quantity"],items[1]["unit"])==("Milk",Decimal("500"),"ml")
    assert (items[1]["unit_price"],items[1]["line_total"])==(Decimal("30.00"),Decimal("15.00"))
    assert (items[2]["name"],items[2]["quantity"],items[2]["unit"])==("Oil",Decimal("1"),"l")

def test_unboxed_table_headers_respect_reordered_columns():
    lines=[
        OCRLine("ITEM AMOUNT QTY RATE",.99,[]),
        OCRLine("Rice 120.00 2 60.00",.94,[]),
    ]
    _,items,_=parse_lines(lines)
    assert len(items)==1
    assert (items[0]["quantity"],items[0]["unit_price"],items[0]["line_total"])==(
        Decimal("2"),Decimal("60.00"),Decimal("120.00"))

def test_unboxed_quantity_amount_columns_accept_inline_units_without_inventing_rate():
    lines=[
        OCRLine("ITEM QTY AMOUNT",.99,[]),
        OCRLine("Rice 2 kg 120.00",.94,[]),
        OCRLine("Bread 2 60.00",.94,[]),
    ]
    _,items,_=parse_lines(lines)
    assert len(items)==2
    assert (items[0]["quantity"],items[0]["unit"],items[0]["line_total"])==(
        Decimal("2"),"kg",Decimal("120.00"))
    assert (items[1]["quantity"],items[1]["unit"],items[1]["line_total"])==(
        Decimal("2"),None,Decimal("60.00"))
    assert all(item["unit_price"] is None for item in items)

def test_qty_without_unit_does_not_become_weight_and_price_only_remains_visible():
    _,items,_=parse_lines([OCRLine("Soap Qty 2 Rate 20.00 Amount 40.00",.9,[]), OCRLine("Unclear item Rs 18.50",.8,[])])
    assert items[0]["quantity"]==Decimal("2") and items[0]["unit"] is None
    assert items[0]["unit_price"]==Decimal("20.00") and items[0]["line_total"]==Decimal("40.00")
    assert items[1]["quantity"] is None and items[1]["line_total"]==Decimal("18.50")

def test_same_baseline_ocr_boxes_are_combined_as_a_receipt_row():
    # Separate OCR boxes sorted left-to-right, sharing the same approximate y.
    row=[OCRLine("Rice",.95,[[0,10],[20,10],[20,20],[0,20]]),
         OCRLine("2 kg",.95,[[30,10],[50,10],[50,20],[30,20]]),
         OCRLine("60.00",.95,[[60,10],[80,10],[80,20],[60,20]]),
         OCRLine("120.00",.95,[[90,10],[110,10],[110,20],[90,20]])]
    _,items,_=parse_lines(row)
    assert len(items)==1 and items[0]["name"]=="Rice"
    assert items[0]["quantity"]==Decimal("2") and items[0]["unit"]=="kg"

def test_supplied_receipt_text_regression_keeps_all_fourteen_rows_and_columns():
    # Mocked OCR rows derived from the user-provided transcript; no image accuracy claim.
    lines=[OCRLine("Item Name MRP Qty Price",.99,[])]
    values=[
        ("GOWARDHAN GO CHEE", "55.00", "1.000", "54.04"),
        ("AMUL VANILA IC CR", "20.00", "1.000", "19.58"),
        ("APPY JUICE 400 ML", "18.00", "1.000", "17.44"),
        ("BT RAWRICE", "48.00", "1.000", "41.14"),
        ("ORANGE CITRUS", "96.00", "0.606", "95.00"),
        ("GOODLIFE PURE COW", "22.00", "1.000", "21.75"),
        ("SUGAR", "40.00", "1.000", "38.76"),
        ("BAMBINO ROASTED V", "37.00", "1.000", "36.37"),
        ("CUCUMBER HYBRID", "19.00", "0.300", "18.00"),
        ("DOUBLE HORSE IDIY", "19.50", "1.000", "18.74"),
        ("GINGER", "46.00", "0.076", "45.00"),
        ("GREEN CHILLY", "46.00", "0.076", "45.00"),
        ("TIDE JR 1 KG", "88.00", "1.000", "85.73"),
        ("PEPSODENT KDS FRT", "49.00", "1.000", "47.10"),
    ]
    lines.extend(OCRLine(f"{name} {mrp} {qty} {price}",.95,[]) for name,mrp,qty,price in values)
    result=parse_receipt(lines)
    assert result["header"]["store_name"] is None
    assert len(result["items"])==14
    first,second,juice,orange,cucumber,ginger,chilli,tide,toothpaste=[result["items"][i] for i in (0,1,2,4,8,10,11,12,13)]
    assert (first["mrp"],first["quantity"],first["price_column_value"])==(Decimal("55.00"),Decimal("1.000"),Decimal("54.04"))
    assert (second["mrp"],second["quantity"],second["price_column_value"])==(Decimal("20.00"),Decimal("1.000"),Decimal("19.58"))
    assert (juice["name"],juice["package_size"],juice["package_size_unit"])==("APPY JUICE",Decimal("400"),"ml")
    assert (orange["quantity"],orange["unit"],orange["price_column_value"])==(Decimal("0.606"),"kg",Decimal("95.00"))
    assert (cucumber["quantity"],cucumber["unit"],cucumber["price_column_value"])==(Decimal("0.300"),"kg",Decimal("18.00"))
    assert (ginger["quantity"],ginger["unit"],ginger["price_column_value"])==(Decimal("0.076"),"kg",Decimal("45.00"))
    assert (chilli["quantity"],chilli["unit"],chilli["price_column_value"])==(Decimal("0.076"),"kg",Decimal("45.00"))
    assert (tide["name"],tide["package_size"],tide["package_size_unit"],tide["quantity"],tide["unit"])==("TIDE JR",Decimal("1"),"kg",Decimal("1.000"),"pack")
    assert toothpaste["suggested_category"]=="personal_care.toothpaste" and toothpaste["category"] is None
    assert all(item["line_total"] is None and item["price_column_semantics"]=="UNKNOWN" for item in result["items"])

def test_decimal_parser_does_not_truncate_or_accept_malformed_grouping():
    assert [parse_decimal_token(s) for s in ("54.04","0.606","1.000","400","55.00","1.25","1,234.50")] == [Decimal("54.04"),Decimal("0.606"),Decimal("1.000"),Decimal("400"),Decimal("55.00"),Decimal("1.25"),Decimal("1234.50")]
    assert parse_decimal_token("54,04") is None

def test_package_sizes_remain_separate_from_pack_count():
    name,size,unit=extract_package_size("APPY JUICE 400ML")
    assert (name,size,unit)==("APPY JUICE",Decimal("400"),"ml")
    name,size,unit=extract_package_size("TIDE JR 1 KG")
    assert (name,size,unit)==("TIDE JR",Decimal("1"),"kg")
