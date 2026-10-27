"""Import validated factor records from JSON file(s) into the configured PostgreSQL catalog."""
import argparse, csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" if (ROOT / "backend/app").exists() else ROOT))
from app.database.session import SessionLocal
from app.services.emission_factor_service import EmissionFactorService

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    files = args.files or sorted((ROOT / "data/raw/emission_factors").glob("*.json"))
    report = {key: 0 for key in ("Imported", "Updated", "Skipped", "Rejected")}
    with SessionLocal() as db:
        service = EmissionFactorService(db)
        for path in files:
            content = path.read_text(encoding="utf-8-sig")
            if not content.strip():
                report["Skipped"] += 1
                continue
            if path.suffix.casefold() == ".csv":
                records = list(csv.DictReader(content.splitlines()))
                records = []
                for row in csv.DictReader(content.splitlines()):
                    cleaned = {key: (value if value != "" else None) for key, value in row.items()}
                    if cleaned.get("status") is None:
                        cleaned.pop("status", None)
                    records.append(cleaned)
            elif path.suffix.casefold() == ".json":
                records = json.loads(content)
                records = records if isinstance(records, list) else [records]
            else:
                report["Rejected"] += 1
                print(f"Rejected {path}: supported formats are JSON and CSV")
                continue
            for record in records:
                try:
                    report[service.import_record(record)] += 1
                except Exception as exc:
                    db.rollback()
                    report["Rejected"] += 1
                    print(f"Rejected {path}: {exc}")
    for key, count in report.items(): print(f"{key}: {count}")

if __name__ == "__main__": main()
