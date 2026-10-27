# Food factor source

`ghg-per-kg-poore.csv` is the OWID full grapher CSV downloaded on 2026-10-13 from https://ourworldindata.org/grapher/ghg-per-kg-poore.csv?v=1&csvType=full&useColumnShortNames=false. It contains 38 food-category entities with 2010 study reference values based on Poore & Nemecek (2018). OWID chart/data attribution is CC BY; retain attribution to Our World in Data and the original providers. These global average category factors are not product- or India-specific. The SHA-256 checksum is recorded in each imported factor row.

## Reviewed factor input format for other sources

Place reviewed JSON records here for the existing factor importer. Each record must include `category`, `activity_type`, `geography`, `unit`, numeric `factor`, `factor_unit`, `source`, `source_url`, `source_year`, `source_version`, `methodology`, `valid_from`, and `source_license`. `status` may be REVIEW or APPROVED; incomplete or conflicting records are rejected. The JSON example below is documentation only; its values are intentionally absent.

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
