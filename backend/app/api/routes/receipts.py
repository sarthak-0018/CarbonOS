import hashlib, os, uuid, tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.dependencies import get_session
from app.models.domain import Profile, Receipt, ReceiptItem, EmissionFactor, Activity
from app.receipts import validate_image, preprocess_image, parse_receipt, calculate_item, redact_sensitive_text
from app.ocr.base import OCRLine
from app.ocr.ocr_service import get_ocr_provider
from app.services.grocery_normalization import match_product

router=APIRouter(prefix="/api/receipts", tags=["grocery receipts"])
Db=Annotated[Session,Depends(get_session)]
provider=get_ocr_provider()

@router.get("/categories")
def categories(db: Db):
    rows=db.scalars(select(EmissionFactor).where(EmissionFactor.factor_key.like("food_%_kg"),EmissionFactor.geography_code=="GLOBAL",EmissionFactor.status=="APPROVED").order_by(EmissionFactor.factor_key)).all()
    return [{"key":f.factor_key.removeprefix("food_").removesuffix("_kg"),"label":f.category,"factor":float(f.value_kg_co2e_per_unit),"unit":f.activity_unit,"source":f.source_name} for f in rows if f.value_kg_co2e_per_unit is not None]

class ItemPatch(BaseModel):
    product_name: str|None=Field(default=None,min_length=1,max_length=240)
    quantity: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=4)
    unit: str|None=None
    food_category: str|None=None
    line_total: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    unit_price: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    package_size: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=4)
    package_size_unit: str|None=None
    mrp: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    price_column_value: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    price_column_semantics: str|None=Field(default=None,pattern="^(UNKNOWN|UNIT_PRICE|LINE_AMOUNT|USER_CONFIRMED_UNIT_PRICE|USER_CONFIRMED_LINE_AMOUNT)$")

class ItemCreate(BaseModel):
    product_name: str=Field(min_length=1,max_length=240)
    quantity: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=4)
    unit: str|None=None
    line_total: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)

def owned(db, profile_id, receipt_id):
    receipt=db.scalar(select(Receipt).options(selectinload(Receipt.items)).where(Receipt.id==receipt_id,Receipt.profile_id==profile_id))
    if not receipt: raise HTTPException(404,detail={"code":"RESOURCE_NOT_FOUND","message":"Receipt not found"})
    return receipt

def output(receipt):
    items=[{"id":str(i.id),"raw_text":i.raw_text,"product_name":i.normalized_product_name or i.raw_product_name,"quantity":float(i.quantity) if i.quantity is not None else None,"unit":i.quantity_unit,"quantity_unit_inferred":i.quantity_unit_inferred,"package_size":float(i.package_size) if i.package_size is not None else None,"package_size_unit":i.package_size_unit,"mrp":float(i.mrp) if i.mrp is not None else None,"price_column_value":float(i.price_column_value) if i.price_column_value is not None else None,"price_column_semantics":i.price_column_semantics,"suggested_category":i.source_metadata.get("suggested_category"),"unit_price":float(i.unit_price) if i.unit_price is not None else None,"line_total":float(i.line_total) if i.line_total is not None else None,"food_category":i.food_category,"match_method":i.match_method,"match_confidence":float(i.match_confidence) if i.match_confidence is not None else None,"needs_confirmation":not bool(i.food_category),"warnings":i.source_metadata.get("warnings",[]),"emissions_status":i.emissions_status,"emissions_kg_co2e":float(i.emissions_kg_co2e) if i.emissions_kg_co2e is not None else None,"calculation_details":i.calculation_details,"ocr_confidence":float(i.ocr_confidence) if i.ocr_confidence is not None else None,"parsing_confidence":float(i.parse_confidence) if i.parse_confidence is not None else None,"user_corrected":i.user_corrected} for i in receipt.items]
    calculated=[i for i in items if i["emissions_kg_co2e"] is not None]
    warnings=receipt.processing_error.split(" | ") if receipt.processing_error else []
    if receipt.total_amount is None: warnings.append("Receipt total was not detected; review it against the image.")
    return {"id":str(receipt.id),"profile_id":str(receipt.profile_id),"merchant_name":receipt.merchant_name,"store_address":receipt.store_address,"receipt_date":receipt.receipt_date,"invoice_number":receipt.invoice_number,"gstin":receipt.gstin,"subtotal":float(receipt.subtotal) if receipt.subtotal is not None else None,"discount_total":float(receipt.discount_total) if receipt.discount_total is not None else None,"tax_total":float(receipt.tax_total) if receipt.tax_total is not None else None,"total_amount":float(receipt.total_amount) if receipt.total_amount is not None else None,"currency":receipt.currency,"ocr_status":receipt.ocr_status,"processing_error":receipt.processing_error,"calculation_status":receipt.calculation_status,"raw_ocr_text":receipt.raw_ocr_text,"ocr_lines":receipt.ocr_data or [],"ocr_engine":receipt.ocr_engine,"created_at":receipt.created_at,"items":items,"warnings":warnings,"summary":{"calculated_items":len(calculated),"total_items":len(items),"estimated_kg_co2e":sum(i["emissions_kg_co2e"] for i in calculated)}}

@router.post("/scan")
async def scan(request: Request, db: Db):
    try:
        form=await request.form()
        profile_id=UUID(str(form.get("profile_id", "")))
        image=form.get("image")
        if image is None or not hasattr(image,"read"): raise ValueError("IMAGE_REQUIRED")
    except Exception as exc:
        raise HTTPException(422,detail={"code":"INVALID_UPLOAD_FORM","message":"Send multipart fields profile_id and image."}) from exc
    if not db.get(Profile,profile_id): raise HTTPException(404,detail={"code":"PROFILE_NOT_FOUND","message":"Profile not found"})
    max_upload=int(os.getenv("RECEIPT_MAX_UPLOAD_BYTES",str(10*1024*1024)))
    data=await image.read(max_upload+1)
    try:
        fmt, normalized=validate_image(data,image.content_type)
        suffix=Path(getattr(image,"filename","") or "").suffix.lower()
        allowed={"JPEG":{".jpg",".jpeg"},"PNG":{".png"},"WEBP":{".webp"}}
        if suffix and suffix not in allowed[fmt]: raise ValueError("IMAGE_EXTENSION_MISMATCH")
    except ValueError as exc:
        status=503 if str(exc)=="IMAGE_DECODER_UNAVAILABLE" else 400
        raise HTTPException(status,detail={"code":str(exc),"message":"Image decoding is unavailable; install the backend image dependencies." if status==503 else "Choose a valid JPG, PNG or WebP image under 10 MB."}) from exc
    checksum=hashlib.sha256(data).hexdigest()
    existing=db.scalar(select(Receipt).options(selectinload(Receipt.items)).where(Receipt.profile_id==profile_id,Receipt.file_sha256==checksum))
    if existing: return output(existing)
    receipt_id=uuid.uuid4(); storage=Path(os.getenv("RECEIPT_STORAGE_DIR","./uploads/receipts")).resolve(); storage.mkdir(parents=True,exist_ok=True)
    key=f"{receipt_id}{'.jpg' if fmt=='JPEG' else '.png' if fmt=='PNG' else '.webp'}"; target=storage/key
    target.write_bytes(data)
    receipt=Receipt(id=receipt_id,profile_id=profile_id,image_storage_key=key,file_sha256=checksum,raw_ocr_text="",ocr_engine=provider.version,ocr_status="PROCESSING",calculation_status="NOT_CALCULATED",currency="INR")
    db.add(receipt); db.commit()
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg",delete=False) as tmp:
            preprocess_image(normalized).save(tmp,format="JPEG",quality=94); tmp_path=tmp.name
        lines=provider.recognize(tmp_path)
    except Exception as exc:
        receipt.ocr_status="FAILED"; receipt.processing_error="Local OCR provider failed. Check the configured model cache and OCR installation."; db.commit()
        raise HTTPException(503,detail={"code":"OCR_FAILED","message":"Local OCR could not read this image. The receipt was retained so processing can be retried."}) from exc
    finally:
        if "tmp_path" in locals(): Path(tmp_path).unlink(missing_ok=True)
    lines=[OCRLine(redact_sensitive_text(line.text),line.confidence,line.box) for line in lines]
    parsed_result=parse_receipt(lines); raw=parsed_result["raw_ocr_text"]; parsed=parsed_result["items"]; header=parsed_result["header"]
    receipt.raw_ocr_text=raw; receipt.ocr_data=[{"text":line.text,"confidence":line.confidence,"box":line.box} for line in lines]; receipt.ocr_engine=provider.version; receipt.ocr_status="REVIEW_REQUIRED"; receipt.processing_error=" | ".join(header["warnings"]+([header["reconciliation_warning"]] if header["reconciliation_warning"] else [])) or None
    receipt.merchant_name=header["store_name"]; receipt.store_address=header["store_address"]; receipt.receipt_date=header["purchase_date"]; receipt.invoice_number=header["invoice_number"]; receipt.gstin=header["gstin"]; receipt.subtotal=header["subtotal"]; receipt.discount_total=header["discount_total"]; receipt.tax_total=header["tax_total"]; receipt.total_amount=header["total_amount"]; receipt.currency=header["currency"] or "INR"
    for index,row in enumerate(parsed):
        receipt.items.append(ReceiptItem(line_index=index,raw_text=row["raw_text"],raw_product_name=row["name"],normalized_product_name=row["normalized_name"],quantity=row["quantity"],quantity_unit=row["unit"],quantity_unit_inferred=row["unit_inferred"],package_size=row["package_size"],package_size_unit=row["package_size_unit"],mrp=row["mrp"],price_column_value=row["price_column_value"],price_column_semantics=row["price_column_semantics"],source_metadata=row["metadata"],unit_price=row["unit_price"],line_total=row["line_total"],food_category=row["category"],match_method=row["match_method"],match_confidence=row["match_confidence"],ocr_confidence=row["confidence"],parse_confidence=row["parsing_confidence"],quantity_evidence="INFERRED" if row["unit_inferred"] else "OCR",emissions_status="NEEDS_REVIEW",calculation_details={}))
    db.commit(); db.refresh(receipt)
    return output(receipt)

@router.get("")
def history(profile_id: UUID, db: Db):
    rows=db.scalars(select(Receipt).options(selectinload(Receipt.items)).where(Receipt.profile_id==profile_id).order_by(Receipt.created_at.desc()).limit(100)).all()
    return [output(r) for r in rows]

@router.get("/{receipt_id}")
def detail(receipt_id: UUID, profile_id: UUID, db: Db): return output(owned(db,profile_id,receipt_id))

@router.patch("/{receipt_id}/items/{item_id}")
def edit_item(receipt_id: UUID,item_id: UUID,profile_id: UUID,payload: ItemPatch,db: Db):
    receipt=owned(db,profile_id,receipt_id); item=next((x for x in receipt.items if x.id==item_id),None)
    if not item: raise HTTPException(404,detail={"code":"ITEM_NOT_FOUND","message":"Receipt item not found"})
    if receipt.confirmed_at: raise HTTPException(409,detail={"code":"RECEIPT_CONFIRMED","message":"This confirmed receipt is read-only."})
    changes=payload.model_dump(exclude_unset=True)
    if changes.get("unit") not in (None,"kg","g","l","ml","each","packet","pack","pouch","bottle","box","tin","bag","bunch","dozen"): raise HTTPException(422,detail={"code":"UNSUPPORTED_UNIT","message":"Choose a supported grocery unit."})
    if "product_name" in changes:
        item.normalized_product_name=changes["product_name"]
        if "food_category" not in changes:
            match=match_product(changes["product_name"])
            item.food_category=match["category"]; item.match_method=match["method"]; item.match_confidence=match["confidence"]
    if "quantity" in changes: item.quantity=changes["quantity"]
    if "unit" in changes:
        item.quantity_unit=changes["unit"]
        item.quantity_unit_inferred=False
    if "food_category" in changes:
        category=changes["food_category"]
        if category and not db.scalar(select(EmissionFactor.id).where(EmissionFactor.factor_key=="food_"+category.lower().replace(" ","_")+"_kg",EmissionFactor.geography_code=="GLOBAL",EmissionFactor.status=="APPROVED")):
            raise HTTPException(422,detail={"code":"FACTOR_UNAVAILABLE","message":"Choose a category with an approved imported factor."})
        item.food_category=category
        item.match_method="MANUAL" if category else None
        item.match_confidence=None
    if "line_total" in changes: item.line_total=changes["line_total"]
    if "unit_price" in changes: item.unit_price=changes["unit_price"]
    if "package_size" in changes: item.package_size=changes["package_size"]
    if "package_size_unit" in changes: item.package_size_unit=changes["package_size_unit"]
    if "mrp" in changes: item.mrp=changes["mrp"]
    if "price_column_value" in changes: item.price_column_value=changes["price_column_value"]
    if "price_column_semantics" in changes:
        item.price_column_semantics=changes["price_column_semantics"]
        if changes["price_column_semantics"] in ("UNIT_PRICE","USER_CONFIRMED_UNIT_PRICE"): item.unit_price=item.price_column_value
        elif changes["price_column_semantics"] in ("LINE_AMOUNT","USER_CONFIRMED_LINE_AMOUNT"): item.line_total=item.price_column_value
        else: item.unit_price=None; item.line_total=None
    item.user_corrected=True; item.quantity_evidence="USER_CORRECTED"
    item.emissions_kg_co2e=None; item.matched_factor_id=None; item.calculation_details={}; item.emissions_status="NEEDS_REVIEW"
    db.commit()
    return output(owned(db,profile_id,receipt_id))

@router.post("/{receipt_id}/items")
def add_item(receipt_id: UUID,profile_id: UUID,payload: ItemCreate,db: Db):
    receipt=owned(db,profile_id,receipt_id)
    if receipt.confirmed_at: raise HTTPException(409,detail={"code":"RECEIPT_CONFIRMED","message":"This confirmed receipt is read-only."})
    if payload.unit not in (None,"kg","g","l","ml","each","packet","pack","pouch","bottle","box","tin","bag","bunch","dozen"): raise HTTPException(422,detail={"code":"UNSUPPORTED_UNIT","message":"Choose a supported grocery unit."})
    item=ReceiptItem(line_index=max((row.line_index for row in receipt.items),default=-1)+1,raw_text=payload.product_name,raw_product_name=payload.product_name,normalized_product_name=payload.product_name,quantity=payload.quantity,quantity_unit=payload.unit,line_total=payload.line_total,quantity_evidence="USER_ENTERED",emissions_status="NEEDS_REVIEW",user_corrected=True,calculation_details={})
    receipt.items.append(item); db.commit(); return output(owned(db,profile_id,receipt_id))

@router.delete("/{receipt_id}/items/{item_id}")
def remove_item(receipt_id: UUID,item_id: UUID,profile_id: UUID,db: Db):
    receipt=owned(db,profile_id,receipt_id)
    if receipt.confirmed_at: raise HTTPException(409,detail={"code":"RECEIPT_CONFIRMED","message":"This confirmed receipt is read-only."})
    item=next((row for row in receipt.items if row.id==item_id),None)
    if not item: raise HTTPException(404,detail={"code":"ITEM_NOT_FOUND","message":"Receipt item not found"})
    receipt.items.remove(item); db.delete(item); db.commit(); return output(owned(db,profile_id,receipt_id))

class ReceiptPatch(BaseModel):
    merchant_name: str|None=Field(default=None,max_length=200)
    store_address: str|None=Field(default=None,max_length=1000)
    receipt_date: date|None=None
    invoice_number: str|None=Field(default=None,max_length=100)
    gstin: str|None=Field(default=None,max_length=20)
    currency: str|None=Field(default=None,max_length=8,pattern="^INR$")
    subtotal: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    discount_total: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    tax_total: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    total_amount: Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)

@router.patch("/{receipt_id}")
def edit_receipt(receipt_id: UUID,profile_id: UUID,payload: ReceiptPatch,db: Db):
    receipt=owned(db,profile_id,receipt_id)
    if receipt.confirmed_at: raise HTTPException(409,detail={"code":"RECEIPT_CONFIRMED","message":"This confirmed receipt is read-only."})
    for field,value in payload.model_dump(exclude_unset=True).items(): setattr(receipt,field,value)
    db.commit(); return output(owned(db,profile_id,receipt_id))

@router.get("/{receipt_id}/image")
def receipt_image(receipt_id: UUID,profile_id: UUID,db: Db):
    receipt=owned(db,profile_id,receipt_id)
    storage=Path(os.getenv("RECEIPT_STORAGE_DIR","./uploads/receipts")).resolve()
    target=(storage/Path(receipt.image_storage_key).name).resolve()
    if storage not in target.parents or not target.is_file(): raise HTTPException(404,detail={"code":"IMAGE_NOT_FOUND","message":"Receipt image is unavailable."})
    media_type={".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}.get(target.suffix.lower(),"application/octet-stream")
    return FileResponse(target,media_type=media_type,filename="receipt"+target.suffix.lower(),content_disposition_type="inline")

@router.post("/{receipt_id}/process")
def retry_processing(receipt_id: UUID,profile_id: UUID,db: Db):
    receipt=owned(db,profile_id,receipt_id)
    if receipt.ocr_status=="CONFIRMED": raise HTTPException(409,detail={"code":"RECEIPT_CONFIRMED","message":"Confirmed receipts cannot be reprocessed."})
    if receipt.ocr_status not in ("FAILED","PROCESSING"): raise HTTPException(409,detail={"code":"RETRY_NOT_ALLOWED","message":"Only failed or interrupted processing can be retried."})
    storage=Path(os.getenv("RECEIPT_STORAGE_DIR","./uploads/receipts")).resolve(); target=(storage/Path(receipt.image_storage_key).name).resolve()
    if storage not in target.parents or not target.is_file(): raise HTTPException(404,detail={"code":"IMAGE_NOT_FOUND","message":"Receipt image is unavailable."})
    receipt.ocr_status="PROCESSING"; receipt.processing_error=None; db.commit()
    tmp_path=None
    try:
        _, normalized=validate_image(target.read_bytes(),None)
        with tempfile.NamedTemporaryFile(suffix=".jpg",delete=False) as tmp:
            preprocess_image(normalized).save(tmp,format="JPEG",quality=94); tmp_path=tmp.name
        rows=provider.recognize(tmp_path); rows=[OCRLine(redact_sensitive_text(line.text),line.confidence,line.box) for line in rows]; result=parse_receipt(rows)
        receipt.raw_ocr_text=result["raw_ocr_text"]; receipt.ocr_data=[{"text":line.text,"confidence":line.confidence,"box":line.box} for line in rows]; receipt.ocr_engine=provider.version; receipt.ocr_status="REVIEW_REQUIRED"
        header=result["header"]
        receipt.merchant_name=header["store_name"]; receipt.receipt_date=header["purchase_date"]; receipt.invoice_number=header["invoice_number"]; receipt.gstin=header["gstin"]; receipt.subtotal=header["subtotal"]; receipt.discount_total=header["discount_total"]; receipt.tax_total=header["tax_total"]; receipt.total_amount=header["total_amount"]; receipt.currency=header["currency"]
        receipt.items.clear()
        for index,row in enumerate(result["items"]):
            receipt.items.append(ReceiptItem(line_index=index,raw_text=row["raw_text"],raw_product_name=row["name"],normalized_product_name=row["normalized_name"],quantity=row["quantity"],quantity_unit=row["unit"],quantity_unit_inferred=row["unit_inferred"],package_size=row["package_size"],package_size_unit=row["package_size_unit"],mrp=row["mrp"],price_column_value=row["price_column_value"],price_column_semantics=row["price_column_semantics"],source_metadata=row["metadata"],unit_price=row["unit_price"],line_total=row["line_total"],food_category=row["category"],match_method=row["match_method"],match_confidence=row["match_confidence"],ocr_confidence=row["confidence"],parse_confidence=row["parsing_confidence"],quantity_evidence="INFERRED" if row["unit_inferred"] else "OCR",emissions_status="NEEDS_REVIEW",calculation_details={}))
        receipt.processing_error=" | ".join(header["warnings"]+([header["reconciliation_warning"]] if header["reconciliation_warning"] else [])) or None
        db.commit(); return output(owned(db,profile_id,receipt_id))
    except Exception as exc:
        db.rollback(); receipt=owned(db,profile_id,receipt_id); receipt.ocr_status="FAILED"; receipt.processing_error="Local OCR retry failed. Check the configured model cache and OCR installation."; db.commit()
        raise HTTPException(503,detail={"code":"OCR_FAILED","message":"Local OCR retry failed. The receipt remains available for another retry."}) from exc
    finally:
        if tmp_path: Path(tmp_path).unlink(missing_ok=True)

@router.post("/{receipt_id}/confirm")
def confirm(receipt_id: UUID,profile_id: UUID,db: Db):
    receipt=owned(db,profile_id,receipt_id)
    if any(not (item.normalized_product_name or item.raw_product_name or "").strip() for item in receipt.items):
        raise HTTPException(422,detail={"code":"ITEM_DESCRIPTION_REQUIRED","message":"Every receipt row needs a product description or must be removed before confirmation."})
    for item in receipt.items: calculate_item(db,item)
    receipt.ocr_status="CONFIRMED"; receipt.confirmed_at=receipt.confirmed_at or datetime.now(timezone.utc)
    statuses=[i.emissions_status for i in receipt.items]
    receipt.calculation_status="COMPLETE" if statuses and all(s=="CALCULATED" for s in statuses) else "PARTIAL" if any(s=="CALCULATED" for s in statuses) else "UNAVAILABLE"
    # Confirmed item records enter the existing activity timeline once per receipt row.
    if receipt.confirmed_at and receipt.calculation_status != "UNAVAILABLE":
        for item in receipt.items:
            if item.emissions_status != "CALCULATED": continue
            exists=db.scalar(select(Activity.id).where(Activity.profile_id==profile_id,Activity.details["receipt_item_id"].as_string()==str(item.id)))
            if exists: continue
            mass=float(item.calculation_details.get("mass_kg",0))
            if mass<=0: continue
            db.add(Activity(profile_id=profile_id,activity_type="food_"+item.food_category.lower().replace(" ","_")+"_kg",quantity=mass,unit="kg",occurred_at=datetime.combine(receipt.receipt_date,datetime.min.time(),tzinfo=timezone.utc) if receipt.receipt_date else receipt.created_at,source="OCR",confidence=item.parse_confidence,details={"frequency":"ONE_TIME","receipt_id":str(receipt.id),"receipt_item_id":str(item.id),"calculation_details":item.calculation_details}))
    db.commit(); return output(owned(db,profile_id,receipt_id))

@router.post("/{receipt_id}/recalculate")
def recalculate(receipt_id: UUID,profile_id: UUID,db: Db):
    receipt=owned(db,profile_id,receipt_id)
    for item in receipt.items: calculate_item(db,item)
    db.commit(); return output(owned(db,profile_id,receipt_id))
