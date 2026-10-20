# Pyeongtaek measurements, 2024

The prepared comparison uses **Songbuk-dong (송북동), AirKorea station 131344**. It is an identified urban-air monitoring station in Pyeongtaek, Gyeonggi Province. It represents that station's measurements; it is not a citywide average. The application label is `Pyeongtaek · Songbuk-dong`.

The source is the [Gyeonggi Institute of Health and Environment's public station-query interface](https://air.gg.go.kr/default/esData.do?mCode=A010010000), independently retrieved in twelve monthly JSON responses. These are the province's **raw hourly observations**, which may differ from nationally ratified data. No NIER final-ratification claim is made.

The actual concentration product is catalogued as [Gyeonggi's 1-hour average measurements, DATA.GO.KR 15122939](https://www.data.go.kr/data/15122939/fileData.do), corresponding to [Gyeonggi dataset E20A4WR0UKVQFVTXNT7D33593740](https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=E20A4WR0UKVQFVTXNT7D33593740&infSeq=1). The catalog identifies the same provincial institute as producer and explicitly describes raw hourly station concentrations for PM₂.₅ and the other pollutants. This is a concentration product, not reconstructed AQI. The unrestricted license is tied to that identified product, rather than inferred from the monitoring site's general footer.

The portal's direct archive endpoint returned HTTP 502 during acquisition. Its producer's monitoring page exposes the working public `getByLoc` station-query interface. The script uses the exact documented fields `op=getByLoc`, `locCd=131344`, `typeCd=1`, and monthly `fromDt`/`toDt` dates. The province's station-list response places `131344` among the six monitors in Pyeongtaek (provincial city code 7). The API currently corrupts Korean names to question marks, but retains the station identifiers; the Songbuk-dong name and national station code are independently identifiable in AirKorea's public station metadata. No AirKorea concentration observations are used in the published record.

Each original provincial response is retained in `data/pyeongtaek/.cache/gyeonggi-songbuk-2024-*.json`, with actual byte count, SHA-256, request fields and retrieval metadata. Ordinary public session/CSRF values are obtained at runtime and are not saved in source metadata or the script. No login, private API key or AWS account is needed. Each monthly response has the expected hourly rows plus three separately identified maximum/minimum/mean rows; those three summaries are excluded from the observation arrays.

| Period | Valid hours | Expected hours | Capture |
| --- | ---: | ---: | ---: |
| Common UTC year | 8,119 | 8,784 | 92.429% |
| UTC winter: January–February, December | 2,099 | 2,184 | 96.108% |
| UTC spring: March–May | 2,170 | 2,208 | 98.279% |
| UTC summer: June–August | 1,768 | 2,208 | 80.072% |
| UTC autumn: September–November | 2,082 | 2,184 | 95.330% |
| Original local calendar year | 8,128 | 8,784 | 92.532% |

The monitor passes the existing rule of at least 75% capture in the UTC year and every meteorological season. Monthly coverage remains visible. August has 383 valid hours out of 744, or **51.478%**, including a continuous 341-hour gap. An [official August maintenance notice](https://www.airkorea.or.kr/web/board/1/956/?pMENU_NO=197&page=11) lists Songbuk-dong's shutdown from 16–30 August after its cooling system failed. This corresponds to the missing interval starts from 16 August 09:00 through 30 August 13:00 KST under the stated timestamp interpretation. The affected summer is sufficiently complete for the project's seasonal selection rule, while the gap remains relevant when comparing August and short pollution episodes.

An earlier national-source candidate was Bijeon-dong (비전동), station 131341. It failed the same seasonal selection rule: annual UTC capture was 81.148%, but winter capture was 70.742%. The national AirKorea source also carries a restrictive license and was superseded by independently acquired provincial observations. That candidate's audit is retained locally; its observations are not mixed into this comparison. Songbuk-dong was chosen for seasonal completeness, not its concentration level.

## Timestamps

The original provincial `dataDt` labels run from `2024010100` to `2024123123`, with exactly 24 labels, **00–23**, for every source calendar day. **The original labels are preserved without a one-hour shift.** Nine hours are subtracted only when converting KST to UTC.

The [province's public display code](https://air.gg.go.kr/default/esData.do?mCode=A010010000) explicitly adds one to a numeric `dataDt` value for presentation, so those native observations appear as hours 01–24 in its table. That explains the displayed convention without importing the national Excel export's timestamp interpretation. A separate physical interval-start/end dictionary was not located. Daily comparisons retain the source's original 00–23 day grouping, and that limitation is recorded in `timeConvention`.

The full local calendar year is retained in `localYear`, beginning at `2023-12-31T15:00:00Z`, with 8,784 hourly slots. The common UTC array is exactly `localYear.values[9:]` followed by nine nulls. Those final nine UTC hours require the next local year's source data and remain unavailable. The Seoul archive is unchanged.

## Zero observations and missing values

The provincial source contains **644 literal numeric PM₂.₅ zeros**, or 7.923% of its 8,128 reported local-year values. The largest monthly counts are July (188) and September (191). The longest continuous zero run is 39 hours, labelled 21 September 21:00 through 23 September 11:00 KST in the original `dataDt` grid.

All 644 zeros are explicit numeric tokens in the original provincial `pm25` fields, distinct from missing tokens. PM₁₀ varies at those same times. This confirms that the zeros were not introduced by filling missing source rows or by a parser applying zero across all channels. It does not establish that the reported PM₂.₅ zeros represent particle-free air. The provincial response has no per-reading QA flags or detection-limit explanation, and no official notice was located that explains those particular zero runs. They are retained and the visible `qaStatus` identifies the caveat.

Blank, dash, `-999`, nonnumeric, nonfinite or negative readings become null. No interpolation, imputation, smoothing, arbitrary upper cutoff or replacement of reported zeros is applied. The selected year contains 656 missing PM₂.₅ observations and no negative or nonfinite reported values. Duplicate source hours are rejected.

## License and attribution

The [official provincial-product catalog](https://www.data.go.kr/data/15122939/fileData.do) and its [machine-readable metadata](https://www.data.go.kr/catalog/15122939/fileData.json) specify **unrestricted reuse (이용허락범위 제한 없음)**. The producer, raw hourly concentration description and station-query observations establish the mapping to the identified provincial measurement product. Source metadata records that product-level mapping explicitly. No CC0 label is invented, and AirKorea's separate restrictive final-confirmed-data license is not relabelled.

Attribution: Source: Gyeonggi Institute of Health and Environment, Gyeonggi Air Quality Information Service; raw hourly PM₂.₅ observations, Songbuk-dong (송북동), Pyeongtaek, station 131344, 2024.

## Files and verification

- `research/acquire_pyeongtaek_2024.py` acquires and audits monthly provincial responses using only the Python standard library. Run it from any directory. Cached response hashes and request fields are verified before reuse. `--refresh` retrieves the public source again, obtaining its public session values at runtime.
- `data/comparisons/pyeongtaek-2024.json` is the compact application record, with both the common UTC array and original local-year values.
- `data/pyeongtaek/quality-2024.json` records monthly provincial-source hashes, source row counts, excluded summary rows, capture, time convention and provenance.

An independent check reopens all twelve original provincial JSON responses, verifies the response hashes, rebuilds the year from its unique original `dataDt` labels, and compares every PM₂.₅ observation with the packaged `localYear` array. The raw local-year array has 8,784 source labels, 8,128 reported values and 644 numeric zeros. The UTC shift, monthly/seasonal capture and station query fields are checked separately.

Published application record (LF line endings): **72,737 bytes**. SHA-256: `74b8389f0071c99ebca98366b1195ffe4cdd0847f231a177cd677fe737c8b7cc`. The acquisition audit also preserves the identity of its original prepared output before line-ending normalization.
