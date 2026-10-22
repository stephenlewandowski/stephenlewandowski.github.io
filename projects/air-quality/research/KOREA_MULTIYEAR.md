# Seoul and Pyeongtaek: 2023 and 2025 hourly PM₂.₅

Acquired on 23 October 2026 from the same municipal/provincial products used for 2024. Each original local calendar year has 8,760 hourly labels, spans all twelve months, and includes all four meteorological seasons.

| City | Year | Valid local-year hours | Capture | Lowest seasonal capture | Longest missing run |
| --- | --- | ---: | ---: | ---: | ---: |
| Seoul network | 2023 | 8,749 | 99.874% | 99.634% | 3 hours |
| Seoul network | 2025 | 8,748 | 99.863% | 99.771% | 2 hours |
| Pyeongtaek, Songbuk-dong | 2023 | 8,583 | 97.979% | 96.429% | 42 hours |
| Pyeongtaek, Songbuk-dong | 2025 | 8,530 | 97.374% | 94.537% | 81 hours |

These are data capture summaries, not regulatory completeness determinations. The corresponding UTC calendar-year arrays have nine fewer valid hours because the original archives end at 31 December 23:00 KST (14:00 UTC). The last nine UTC hours are null rather than imputed. Each `localYear` and Seoul district supplement retains the complete original local-year grid, starting at 31 December 15:00 UTC of the preceding year.

## Sources and reuse

- [Seoul Open Data Plaza OA-2221](https://data.seoul.go.kr/dataList/OA-2221/S/1/datasetView.do): complete annual ZIPs, 2023 modified 7 November 2025 and 2025 modified 1 April 2026. Download form sequence IDs are 34 and 36. The 2023 CSV is UTF-8 with BOM; the 2025 CSV is CP949. The page grants KOGL Type 1 attribution reuse, including commercial use and adaptation. Both files contain exactly 219,000 district-hour rows, the same 25 district IDs as 2024, and no duplicate station-hours. Archived municipal observations have no per-reading QA flags or explicit national final-ratification status.
- [Gyeonggi Air Quality Information Service](https://air.gg.go.kr/default/esData.do?mCode=A010010000): public monthly station queries for Songbuk-dong, station 131344. Each year has 8,760 original `dataDt` observation labels; 36 non-observation monthly summary rows are excluded. This is the province's raw, pre-confirmation product. The [official DATA.GO.KR catalog 15122939](https://www.data.go.kr/data/15122939/fileData.do) identifies the same provincial producer/product and permits unrestricted reuse; this is product-level catalog evidence, not a website-footer license inference.

The compact deployed records retain request parameters, retrieval timestamps, source response byte counts and SHA-256 hashes, attribution and license evidence. Raw downloads stay in the external research cache. `korea-multiyear-audit.json` records coverage, exclusions, source hashes and output hashes.

## Fixed monitor membership and missingness

Seoul uses an unweighted mean over the same fixed 25 district monitors as 2024, requiring at least 20 valid monitors per hour. Keeping fixed membership avoids changing the network's geographic definition between years. A district with a substantial gap still contributes its valid measurements; no readings are filled in. Network-level annual and seasonal capture exceeds 99.6% in both new local years.

Three district-year records fail the previous 75% every-season district completeness screen. They remain available, with an `eligibleForSeasonalComparison` flag and explicit `seasonCapture` metadata:

- Jung-gu (111121), 2023: winter 50.509%; annual 86.712%.
- Eunpyeong-gu (111281), 2025: winter 64.722%; annual 87.614%.
- Gangseo-gu (111251), 2025: spring 52.355%; annual 82.614%.

The source has 4,531 blank district PM₂.₅ values in 2023 and 6,835 in 2025. No numeric zero, negative, nonnumeric or nonfinite Seoul values were found. Pyeongtaek reports 128 numeric zeros in 2023 (longest run 21 hours) and 229 in 2025 (longest run 16 hours). These are retained as reported because the source supplies no per-reading QA or detection-limit explanation. No interpolation, smoothing, concentration-based trimming or arbitrary upper cutoff is applied.

Original source hour labels are preserved. Seoul does not explicitly document interval-start versus interval-end semantics in the inspected metadata. Gyeonggi exposes labels 00–23 and adds one for its 01–24 display; a separate physical interval-start/end dictionary was not located. Exact hourly co-occurrence therefore retains the existing possible one-hour convention uncertainty.

## Reproduce

From the repository root:

```powershell
python projects/air-quality/research/acquire_korea_multiyear.py
```

The standard-library script verifies cached raw response hashes before reuse. Use `--refresh` to download again, `--years 2023` to select a year, or `--cities seoul` to select a source. The default external cache is the sibling `air-quality-comparison/research/extended` directory. Existing 2024 records and manifests are not rewritten by this acquisition script.
