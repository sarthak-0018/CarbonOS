"""Import the pinned OWID/Poore-Nemecek food category CSV into emission_factors."""
import csv, hashlib, re, sys
from datetime import date
from decimal import Decimal
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend" if (PROJECT_ROOT / "backend/app").exists() else PROJECT_ROOT))
from app.database.session import SessionLocal
from app.models.domain import EmissionFactor

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"data/raw/emission_factors/ghg-per-kg-poore.csv"
URL="https://ourworldindata.org/grapher/ghg-per-kg-poore.csv?v=1&csvType=full&useColumnShortNames=false"
RETRIEVED=date(2026,10,13)
def slug(text): return re.sub(r"[^a-z0-9]+","_",text.casefold()).strip("_")
def main():
    raw=SOURCE.read_bytes(); checksum=hashlib.sha256(raw).hexdigest(); imported=0
    with SOURCE.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if not rows or not {"Entity","Year","Greenhouse gas emissions per kilogram"}.issubset(rows[0]): raise SystemExit("Unexpected OWID CSV schema")
    with SessionLocal() as session:
        for row in rows:
            value=Decimal(row["Greenhouse gas emissions per kilogram"]); entity=row["Entity"].strip(); year=int(row["Year"])
            if not entity or value<=0 or year!=2010: raise SystemExit(f"Invalid source row: {row}")
            key=f"food_{slug(entity)}_kg"
            existing=session.query(EmissionFactor).filter_by(factor_key=key,geography_code="GLOBAL",version=1).first()
            if existing: continue
            session.add(EmissionFactor(factor_key=key,geography_code="GLOBAL",version=1,category=entity[:40],activity_unit="kg",value_kg_co2e_per_unit=value,output_unit="kgCO2e",status="APPROVED",source_name="Our World in Data — Poore & Nemecek (2018)",source_url=URL,source_version="Poore and Nemecek 2018; OWID grapher",data_version="OWID CSV retrieved 2026-10-13",source_license="CC BY 4.0; attribute OWID and Poore & Nemecek",checksum=checksum,accessed_on=RETRIEVED,valid_from=date(2010,1,1),methodology_note="Global average category-level lifecycle emissions, study reference year 2010; may poorly represent Indian supply chains and is not product-specific.",activity_type=key,geography="Global average",unit="kg",factor=value,factor_unit="kgCO2e/kg",source="Our World in Data",source_year=2018,gas="CO2E",reference_period_start=date(2010,1,1),reference_period_end=date(2010,12,31),methodology="Poore and Nemecek (2018); lifecycle greenhouse gas emissions per kg of food product"))
            imported+=1
        session.commit()
    print(f"Inserted {imported} new factors; source rows={len(rows)}; sha256={checksum}")
if __name__=="__main__": main()
