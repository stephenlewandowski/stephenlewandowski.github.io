# Hourly PM2.5, 2023–2025

[Open the interactive comparison](https://stephenlewandowski.github.io/projects/air-quality/).

This project compares measured fine particulate matter (PM2.5) from 2023 through
2025. It explores what changes when the same measurements are summarized over
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
uniform conditions across each city. Coverage varies by city and year. Seoul,
Pyeongtaek, London and Los Angeles cover all seasons in both additional years;
Beijing has larger gaps in 2023 and only a partial 2025 record. The page identifies
records that meet the project's 75% hourly capture rule annually and in every
meteorological season. Partial records remain available with their gaps disclosed.

## What to compare

- Select 2023, 2024 or 2025, then plot hourly measurements, UTC daily means or trailing 8-hour and 24-hour means,
  then select a month or another date range.
- Count hours, calendar days and rolling windows above a chosen concentration,
  including the longest consecutive run of hours above it.
- Compare monthly frequencies and concentration distributions, with valid-data
  denominators and numerical tables alongside the plots.
- Compare full-year statistics with U.S. annual and daily PM2.5 reference levels.
  Export selected hourly measurements or comparison statistics as CSV.

The time series uses a common UTC calendar-year grid for the selected year. Calendar-day threshold
counts can use UTC or fixed local standard time; the U.S. standards table always
uses the full local standard-time year, independently of the selected chart dates.

The U.S. panel is a one-year historical comparison, not an attainment
determination. The standards use three-year statistics and require suitable site
measurements and additional quality checks. Seoul's network mean is context only;
its district selector provides individual site records. Hourly and rolling-window
threshold counts are exploratory measures, not federal PM2.5 regulatory limits.

## Gaps and source limitations

Missing measurements remain gaps; no model estimates or interpolated values are
added. Reported zeros remain zero. Pyeongtaek's 2024 record includes an August
outage; all three years contain reported zeros without per-reading quality flags
or a supplied detection-limit explanation. Seoul retains the same 25-monitor
network definition in every year, although some individual districts have lower
seasonal capture. The Los Angeles hourly monitor is distinct from the site's
primary daily monitor, and its 2025 comparability exclusion request limits
regulatory interpretation. Consult the [timeline and coverage notes](data/TIMELINE.md)
when comparing years, short periods or zeros.

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
