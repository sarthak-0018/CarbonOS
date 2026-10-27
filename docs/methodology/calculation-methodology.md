# Calculation methodology

## Deterministic calculation

For each activity, CarbonOS selects exactly one `APPROVED` factor matching activity key, geography, and effective date. It rejects missing, overlapping, NULL-valued, or unit-incompatible factors. Emissions are `normalized activity quantity × factor`, calculated with decimal arithmetic and rounded to six decimal places. Gas type and output units are retained; CO2 is not labeled CO2e. The calculation version is `carbonos-deterministic-v2`; factor identities and values are snapshotted in category details so later factor versions do not rewrite history.

Frequency normalization is ONE_TIME ×1, DAILY ×365, WEEKLY ×52, MONTHLY ×12, QUARTERLY ×4, YEARLY ×1. Recurring quantities are labeled annualized estimates. One-time quantities remain one-time and are restricted to the requested date window. Petrol/diesel vehicle emissions convert distance to litres with user-entered km/litre efficiency, then apply the saved fuel factor. Appliance estimates are not currently auto-summed.

The Carbon Memory dashboard shows a monthly average for recurring activities by dividing their annualized emissions by 12. One-time activities are excluded from that average and shown separately for the selected dates. Gas values (CO₂e, CO₂, CH₄, N₂O) are presented separately; they are not added into a single total because CO₂e is an equivalent-gas measure while the other rows can be gas-specific measurements.

## Partial results

Each activity with a missing factor is retained in the session's `missing_factors` response. Other activities with valid factors are calculated and saved. Sessions report `PARTIAL` for missing factors or CO2-only/mixed-gas results, and `UNAVAILABLE` if no category could be calculated. Mixed gas totals remain separate. An empty period is unavailable rather than a zero footprint.

## Data quality

The score is a deterministic source-weighted coverage indicator, not a scientific confidence estimate: directly metered BILL_UPLOAD/INTEGRATION activities score 100, USER_ENTERED activities 80, and ESTIMATED activities 40; the session score is the activity-count-weighted mean. Breakdown counts actual, user_entered, and estimated activities. Receipt/OCR and AI-suggested data are not currently used for footprint calculations. Missing-factor activities are included in this source score and surfaced separately.
