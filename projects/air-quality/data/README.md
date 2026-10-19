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

Source-specific provenance, download dates, quality decisions and source hashes
are retained within each JSON. No API key is embedded or required by visitors.

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

## Reproduce

From the website repository root, acquisition scripts write intermediate files
under the ignored `projects/air-quality/data/seoul/` and `data/comparisons/` folders:

```powershell
python projects/air-quality/research/acquire_seoul_2024.py
python projects/air-quality/research/acquire_comparisons_2024.py beijing london
python scripts/build_air_quality_data.py --source-root projects/air-quality
node --test scripts/test_air_quality.mjs
python scripts/check_site.py
```

Consult the comparison acquisition script's arguments for selecting sources.
London annual RData archives require a local R installation for decoding; R is
used only during preparation. The website itself uses plain HTML, CSS and
JavaScript and serves the retained JSON files directly.
