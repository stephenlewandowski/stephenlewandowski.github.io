# Hourly PM2.5 in 2024

[Open the interactive comparison](https://stephenlewandowski.github.io/projects/air-quality/).

This project compares measured fine particulate matter (PM2.5) across all seasons
of 2024. It explores what changes when the same measurements are summarized over
an hour, a day or a year. Concentrations are reported in micrograms per cubic
meter (µg/m³), without conversion to an air-quality index.

## Measurements

The comparison includes Seoul, Pyeongtaek, Beijing, London and Los Angeles.
Seoul defaults to an equal-weight mean of its 25 district monitors, requiring at
least 20 valid readings per hour; each district can also be selected individually.
The other city labels identify single monitoring locations:

- Pyeongtaek: Songbuk-dong.
- Beijing: AirNow location distributed through OpenAQ (location 8833).
- London: Lewisham–Honor Oak Park (HP1).
- Los Angeles: North Main Street (EPA AQS 06-037-1103, continuous monitor POC 3).

These records describe monitoring locations, rather than population exposure or
uniform conditions across each city. Each included record meets the project's
75% hourly capture rule for the full year and each meteorological season.

## What to compare

- Plot hourly measurements, UTC daily means or trailing 8-hour and 24-hour means,
  then select a month or another date range.
- Count hours, calendar days and rolling windows above a chosen concentration,
  including the longest consecutive run of hours above it.
- Compare monthly frequencies and concentration distributions, with valid-data
  denominators and numerical tables alongside the plots.
- Compare full-year statistics with U.S. annual and daily PM2.5 reference levels.
  Export selected hourly measurements or comparison statistics as CSV.

The time series uses a common UTC calendar-year grid. Calendar-day threshold
counts can use UTC or fixed local standard time; the U.S. standards table always
uses the full local standard-time year, independently of the selected chart dates.

The U.S. panel is a one-year historical comparison, not an attainment
determination. The standards use three-year statistics and require suitable site
measurements and additional quality checks. Seoul's network mean is context only;
its district selector provides individual site records. Hourly and rolling-window
threshold counts are exploratory measures, not federal PM2.5 regulatory limits.

## Gaps and source limitations

Missing measurements remain gaps; no model estimates or interpolated values are
added. Reported zeros remain zero. Pyeongtaek's record includes an August outage
and long runs of reported zeros without per-reading quality flags or a supplied
detection-limit explanation. The Los Angeles hourly monitor is distinct from
the site's primary daily monitor. Consult the source notes when comparing short
periods or interpreting zeros.

See [data sources, calculation methods and reproduction instructions](data/README.md)
and the [data manifest](data/manifest.json) for station details, coverage, source
hashes and downloadable measurements. The live page includes source notes beside
the comparison.

## Development

The page uses plain HTML, CSS and JavaScript modules. Archived JSON measurements
are served with the site; visitors need no API key or external data request.

From the repository root:

```sh
node --test scripts/test_air_quality.mjs scripts/test_pm25_benchmarks.mjs
python scripts/check_air_quality_data.py
python scripts/check_site.py
git diff --check
```

The [data README](data/README.md#reproduce) documents acquisition and rebuild
commands. Preserve the distinction between exploratory counts and the U.S.
standards calculation when changing the interface or calculations.
