# Food emission factors

The MVP imports the Our World in Data grapher **Greenhouse gas emissions per kilogram of food product**, based on Poore and Nemecek (2018). Source CSV: https://ourworldindata.org/grapher/ghg-per-kg-poore.csv?v=1&csvType=full&useColumnShortNames=false. Local source file: `data/raw/emission_factors/ghg-per-kg-poore.csv`; retrieved 2026-10-13. The CSV contains 37 entities, all with 2010 reference-year values. OWID data visualizations and code are CC BY; cite Our World in Data and the underlying data providers, Joseph Poore and Thomas Nemecek (2018).

Each approved imported value is stored in the existing `emission_factors` table as kgCO2e per kg, geography `GLOBAL`, with source URL, source version, retrieval date, checksum, study reference year, and methodology. Results are **estimated global category-level lifecycle proxies**, not product-specific or India-specific footprints. Factors may be poor proxies for Indian products and supply chains. The UI requires a user to choose an available dataset category; it does not infer product aliases. Missing or unsupported quantities/categories remain unestimated.

Only kg and g are converted to mass. No liquid density is assumed. Multipacks with explicit weight are parsed as a total mass when the receipt format is recognized; a pack count without net mass remains uncalculated.
