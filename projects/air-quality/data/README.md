# Hourly PM2.5 comparison, 2024

This page uses archived measurements on a UTC calendar-year grid of 8,784 hours.
The manifest identifies the included records, file hashes, annual capture and
capture in all four meteorological seasons. At least 75% of the expected hours
must be present in the year and in each season. The threshold is a documented
selection rule for this teaching figure, not a claim of regulatory certification.

Seoul is required. Cities with an incomplete seasonal record are omitted from the
interactive comparison. The number of cities is secondary to covering the year.

## Records and attribution

- **Seoul Metropolitan Government, Seoul Open Data Plaza, OA-2221.**
  [2024 hourly archive](https://data.seoul.go.kr/dataList/OA-2221/S/1/datasetView.do),
  modified 7 November 2025. KOGL Type 1: attribution required; reuse and adaptation
  allowed. The series is an equal average of available readings from the 25
  district monitors, requiring at least 20 monitors per hour. Each monitor meets
  the year/season capture rule. It is not population weighted. The source includes
  no per-observation quality flags or explicit national ratification status.
- **Beijing, AirNow measurements distributed by OpenAQ, location 8833.**
  [Location and source information](https://explore.openaq.org/locations/8833).
  The source metadata lists US Public Domain. This is one monitoring location,
  not a city-wide average. Raw source hashes and URLs accompany the hourly series.
- **London Air Quality Network / Imperial College London, HP1, Lewisham – Honor
  Oak Park.** The [annual archive](https://londonair.org.uk/r_data/HP1_2024.RData)
  provides an urban-background station's PM2.5 readings in GMT. The network's
  [documentation](https://api.erg.ic.ac.uk/AirQuality/Information/Documentation/pdf)
  specifies Open Government Licence v2; the RData file embeds no separate license
  or per-reading ratification status. Measurements may be revised by the provider.
- **Pyeongtaek, Songbuk-dong (송북동), station 131344.** The Gyeonggi Institute of
  Health and Environment supplies provincial hourly concentrations. Its
  [government catalog](https://www.data.go.kr/data/15122939/fileData.do) permits
  unrestricted reuse and warns that these raw observations may differ from
  final nationally validated data. The original provincial 00–23 timestamps
  are preserved. The full local-year source is retained for the standards panel.
  It has 8,119 valid UTC hours (92.429%); each meteorological season exceeds
  80%. August has only 51.478% capture and a 341-hour gap; an
  [official notice](https://www.airkorea.or.kr/web/board/1/956/?pMENU_NO=197&page=11)
  identifies an air-conditioning failure from 16–30 August. Gaps remain missing.
  The source reports 644 zero values, including a 39-hour run; these are retained
  as reported, with no per-reading quality flags or detection-limit explanation
  supplied. The separately examined final AirKorea archive carries
  a no-derivatives condition and is not the source of the published extract.
  [Acquisition and quality notes](../research/PYEONGTAEK_2024.md) and
  [audit](../research/PYEONGTAEK_2024_AUDIT.json) document the provincial source.
- **Los Angeles–North Main Street, EPA AQS 06-037-1103, parameter 88101, POC 3.**
  [EPA AirData](https://aqs.epa.gov/aqsweb/airdata/download_files.html) supplies the
  hourly archive and site/monitor metadata. This is one continuous FEM method 170
  monitor, with 8,598 retained UTC hours (97.883%) and all seasons above 93%.
  Its annual hourly summary is marked Certified. Under the figure's common
  nonnegative rule, 18 reported negative readings are excluded; their original
  values remain in the audit metadata. Informational fireworks and wildfire
  readings remain included. The separate daily FRM POC 1 is the site's primary
  monitor, so this hourly extract does not reproduce the official combined site
  design value. EPA permits free reuse of its public-domain AirData observations.
  [Acquisition and method notes](../research/EPA_LOS_ANGELES_2024.md),
  [audit](../research/EPA_LOS_ANGELES_2024_AUDIT.json) and
  [original selected rows (CSV.gz)](../research/EPA_LOS_ANGELES_2024_SELECTED.csv.gz)
  retain the source evidence.

Source-specific provenance, download dates, quality decisions and source hashes
are retained within each JSON. No API key is embedded or required by visitors.
Prepared data files use LF line endings so their manifest hashes match the
version-controlled and published bytes on every platform; source-response hashes
continue to identify the original downloaded files.

## Calculation and time conventions

All values are PM2.5 concentrations in micrograms per cubic meter. Invalid,
non-finite, negative and missing concentrations are represented by JSON null.
Valid reported zero readings are retained. No gaps are filled or interpolated.

Source timestamps are converted to UTC without silently shifting hour-start and
hour-end labels. Seoul's portal describes hourly averages but does not explicitly
identify that interval convention in the inspected metadata. Its labels are
preserved. Nine unavailable UTC hours at the end of the year remain null because
they fall in the adjacent Korean calendar-year file.

Daily means use UTC days and need 18 of 24 values. A trailing mean includes the
current hour; an 8-hour window needs six valid observations and a 24-hour window
needs eighteen. A full time window must exist, so starting windows remain null
until enough calendar hours have elapsed. Summary statistics and monthly means
use the available hourly values; coverage is always shown separately.

Summary percentiles use linear interpolation between sorted valid observations
(position `(n - 1) × p`). Daily and rolling values are teaching summaries, not an
official reported AQI. The live chart may be exported to long-format hourly CSV.

## Comparisons with U.S. PM2.5 standards

The application applies the current reference levels to 2024 as a historical,
hypothetical comparison. The [EPA NAAQS table](https://www.epa.gov/criteria-air-pollutants/naaqs-table)
and [40 CFR part 50, Appendix N](https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-50/appendix-Appendix%20N%20to%20Part%2050)
were checked on 19 October 2026. The annual primary level is 9.0 µg/m³ and
secondary level 15.0 µg/m³, each assessed using three annual means. The 24-hour
primary/secondary level is 35 µg/m³, assessed using three annual daily 98th
percentiles. No federal 1-hour or 8-hour PM2.5 standard exists.

The standards table always uses the full local calendar year, independently of
the chart's date selection. Days use fixed local standard time (Seoul UTC+9,
Pyeongtaek UTC+9, Beijing UTC+8, London GMT and Los Angeles PST (UTC−8), all
without daylight saving). Hourly values and daily
means are truncated to tenths. A normal day requires at least 18 hours. With
fewer hours, the day is retained only when the sum of reported truncated values
divided by 24 reaches 35.5; this application uses that conservative zero-filled
lower-bound daily mean and discloses the sparse-day exception. It creates no
hourly observations. The 35.5 test is only a validity exception; literal days
above 35 are counted with a strict `>` comparison.

Each quarterly mean averages its valid daily values. The annual component gives
the four quarterly means equal weight. A quarter without daily data makes this
application's annual component unavailable. For continuous daily sampling the
98th percentile is the `ceil(N/50)`th highest valid day, following Appendix N
Table 1; this differs from the interpolated percentiles in the exploratory
summary tables. No final three-year design-value rounding is applied. Displayed
annual components use two decimals, while computations retain full precision.
Quarterly daily capture is reported descriptively, without rounding to integers.

These one-year monitoring extracts do not establish U.S. attainment.
The application does not certify monitor suitability, reproduce an AQS combined
site record, apply exceptional-event exclusions or regulatory data-substitution
tests, or account for prior-standard implementation obligations. Seoul's network
average is explicitly context only: Appendix N calculations apply at site level.

### Seoul district records

`seoul-stations-2024.json` retains all 25 district records and the network mean
from the same audited municipal archive, on the original Korean calendar-year
grid starting `2023-12-31T15:00:00Z`. No observations are changed. It provides the
genuine first nine local-year hours needed by the standards comparison. The
network has 8,780 valid local-year hours; individual districts have 95.879–98.736%
capture and all four seasons at least 75%. For the time series and custom counts,
the browser maps the selected district onto the existing UTC grid, leaving the
final nine unavailable hours null. The original ambiguous hour-label convention
remains a limit on exact day boundaries. Attribution and source/archive hashes
are embedded in the supplemental JSON.

### Threshold counts and distribution views

These use original precision and a customizable strict `>` concentration
threshold. Hourly, calendar-day, trailing 8-hour and trailing 24-hour counts
include their valid denominators; missing values are never assumed below the
threshold. Percentages divide by valid observations. Consecutive-hour runs stop
at a missing value. The default threshold is 35 µg/m³ for comparison, not an
hourly or rolling-window regulatory limit. Decimal accumulation avoids turning
equal decimal inputs into false exceedances through binary summation error.

Custom counts use the selected UTC period and common UTC-grid source. UTC or
fixed local standard-time days can be selected. Full-year local counts retain
boundary days only if they meet the ordinary 18-hour rule; the supplemental
local-year observations and sparse-day exception apply only to the standards table.
For shorter selections a calendar day must fall wholly inside the selected UTC
range. Local counts exclude instants outside local 2024. Rolling counts include
window ends in the selected range and may use earlier source hours; overlapping
windows are not separate events. Monthly bars show the percentage of valid days
above the threshold. Descending concentration curves show strict exceedance
frequency for valid hours or days. Their tables use interpolated percentiles.
The comparison CSV exports the counts, full-year components, quarterly capture
denominators, monthly counts, units and calculation bases.

## Reproduce

From the website repository root, acquisition scripts write intermediate files
under the ignored `projects/air-quality/data/seoul/` and `data/comparisons/` folders:

```powershell
python projects/air-quality/research/acquire_seoul_2024.py
python projects/air-quality/research/acquire_comparisons_2024.py beijing london
python projects/air-quality/research/acquire_pyeongtaek_2024.py
python projects/air-quality/research/acquire_us_city_2024.py
python scripts/build_air_quality_data.py --source-root projects/air-quality
python scripts/build_seoul_station_data.py --source-root projects/air-quality
node --test scripts/test_air_quality.mjs scripts/test_pm25_benchmarks.mjs
python scripts/check_air_quality_data.py
python scripts/check_site.py
```

Consult the comparison acquisition script's arguments for selecting sources.
London annual RData archives require a local R installation for decoding; R is
used only during preparation. The website itself uses plain HTML, CSS and
JavaScript and serves the retained JSON files directly.
