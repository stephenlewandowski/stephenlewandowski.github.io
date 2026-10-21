# Temperature and air pollution in 2024

[Open the daily-pair comparison](https://stephenlewandowski.github.io/projects/air-heat/).

Explore daily averaged PM2.5 on the y-axis against air temperature, relative
humidity, UTCI or WBGT on the x-axis. The five cities match the
[air-quality](../air-quality/README.md) and
[heat-stress](../heat-stress/README.md) projects: Seoul, Pyeongtaek, London,
Beijing and Los Angeles.

## Pairing and views

Hourly records are joined by their actual UTC timestamps. Both daily means use
the same valid hours, requiring at least 18 matches in a complete day. Choose
UTC or fixed local standard time, select dates or a meteorological season, and
choose Seoul's network mean or one of its 25 district monitors.

The scatterplot is colored by season. The application offers:

- Pearson and tied-rank Spearman correlations.
- Linear, quadratic and month-adjusted linear ordinary least-squares models.
- A within-month departure plot, with both axes centered on the selected paired
  days' monthly means, for the month-adjusted model.
- Residuals over time, lag-1 residual correlation and influence diagnostics.
- Separate associations for all five cities, without a pooled cross-city fit.
- Counts of daily PM2.5 at or above a chosen threshold alongside thermal values
  at or above, or at or below, a second threshold.
- Numerical tables, paired-day/model CSV downloads and shareable selections.

The quadratic slope varies with the thermal measure; the table reports its
local slope at the selected sample's mean. Raw-model R² and within-month R²
have different denominators and are labeled separately. No independent-day
p-values or confidence bands are presented because daily records can be
serially correlated.

## Scope

These are environmental associations, not estimates of health-effect
interaction. There are no health outcomes, individual exposure assignments or
military cohort records in this project. The tool cannot establish causal
feedback, physiological synergy or joint health risk.

PM2.5 is measured at the retained monitoring locations. Weather is gridded ERA5
reanalysis, using the same city grid cell for all Seoul districts. The UTCI
option assumes mean radiant temperature equals air temperature. It is **not
published ERA5-HEAT UTCI**; that dataset is documented as a future source.
WBGT has fewer usable hours because the heat project's property-fit filter is
retained. Its paired means can describe a smaller, warmer subset of the year.

Seoul's district archive begins nine hours earlier than the main UTC-year
records; timestamp joining preserves that distinction. Source time-label
uncertainty and the Pyeongtaek outage/reported zeros remain material limits.
Matching-hour means can differ from the standalone projects' means, which
use each variable's own valid hours.

See the [pairing and source notes](data/README.md) and
[manifest](data/manifest.json) for source hashes, coverage, timing conventions
and reproduction. Inputs are reused from the two existing projects and are
served locally; there is no visitor API key or external data request.

## Checks

From the repository root:

```sh
node --test scripts/test_air_heat.mjs
python scripts/check_air_heat_data.py
python scripts/check_site.py
git diff --check
```

The tests include timestamp offsets, overlapping missing hours, minimum daily
capture, tied ranks, known regression fixtures, seasonal confounding and
singular designs. The Python audit independently supplies paired counts and
correlation expectations across all city/metric/calendar combinations.
