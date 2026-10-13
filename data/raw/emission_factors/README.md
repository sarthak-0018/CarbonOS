# Reviewed factor input

Place reviewed JSON records here for the importer. Each record must include `category`, `activity_type`, `geography`, `unit`, numeric `factor`, `factor_unit`, `source`, `source_url`, `source_year`, `source_version`, `methodology`, `valid_from`, and `source_license`. `status` may be REVIEW or APPROVED; incomplete or conflicting records are rejected. No factor file is seeded because no authoritative factor has yet been verified.

Example shape (documentation only; values below are intentionally absent):

```json
{
  "category": "electricity",
  "activity_type": "electricity_grid_kwh",
  "geography": "India",
  "unit": "kWh",
  "factor": null,
  "factor_unit": "kgCO2e/kWh",
  "source": "",
  "source_url": "",
  "source_year": null,
  "source_version": "",
  "methodology": "",
  "valid_from": "YYYY-MM-DD",
  "valid_to": null,
  "uncertainty": null,
  "source_license": "",
  "status": "REVIEW"
}
```

Replace every placeholder only with reviewed source-backed data. This template is intentionally invalid until provenance and a verified numeric factor are supplied.
