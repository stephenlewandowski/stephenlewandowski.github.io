# Temperature and air pollution across years

The archive now includes 2023, 2024 and 2025, with year selectors and yearly coverage/association tables. See the [timeline notes](data/TIMELINE.md) for sources, partial Beijing records, year-by-year models and reproduction. Existing links default to 2024.

The methods section links to the heat comparison's explanation of environmental
conditions, personal exposure, vulnerability and health outcomes. This context
does not add a vulnerability model or health outcomes to the paired records.

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
p-values or confidence bands accompany these interactive fits because daily
records can be serially correlated. The separate follow-up models below use
approximate intervals that account for that dependence.

## Seasonal, weather and hourly analysis

The [follow-up findings](data/ANALYSIS.md) examine temperature and UTCI for the
full 2024 local-standard-time records, using Seoul's network mean. These fixed
results are separate from the upper scatterplot's date and monitor selections.

Separate seasonal LOESS curves show how the association changes within winter,
spring, summer and autumn. The curves are unadjusted descriptive smooths, with
three smoothing spans to show how that choice affects the shape. Their plotted
range runs from each season's observed thermal 10th to 90th percentiles;
sensitivity curves are not confidence bands.

Models compare month differences, current-day wind/humidity/precipitation
adjustment, simultaneous thermal lags from today through three days earlier,
and sensitivities to weather form and prior-day PM2.5. Each comparison uses the
same dates. Approximate Newey–West intervals use actual calendar-day gaps;
missing dates do not become adjacent days. The methods distinguish partial R²
from total R² and a lag-coefficient sum from pollution accumulated over time.
UTCI adjustment holds wind and humidity components of that index fixed.

Seoul's positive within-month UTCI association becomes much smaller after
weather adjustment. Beijing and Los Angeles retain positive adjusted
associations, while London and Pyeongtaek are more sensitive to specification.
The seasonal curves differ within and between cities. These results describe
how concentrations co-vary; they do not identify a causal thermal effect.

The hourly analysis follows the interactive city, monitor, date, season and
threshold controls. It reports paired-hour coverage, hours and days with
overlap, monthly counts and consecutive observed runs. Missing or unselected
hours interrupt runs; midnight alone does not. Boundary flags indicate unknown
continuation. Hourly counts can reveal overlap hidden by daily averages, but
an hourly PM2.5 threshold is not a U.S. hourly regulatory standard.

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
and reproduction. The [follow-up methods](data/ANALYSIS.md) document the added
precipitation archive and model assumptions. All retained inputs and results
are served locally; there is no visitor API key or external data request.

## Checks

From the repository root:

```sh
node --test scripts/test_air_heat.mjs scripts/test_air_heat_hourly.mjs
python scripts/check_air_heat_data.py
python scripts/check_site.py
git diff --check
```

The tests include timestamp offsets, overlapping missing hours, minimum daily
capture, tied ranks, known regression fixtures, seasonal confounding and
singular designs. The Python audit independently supplies paired counts and
correlation expectations across all city/metric/calendar combinations.

The follow-up builder and its numerical tests require NumPy; the original
pairing audit uses only Python's standard library. To reproduce the retained
analysis offline:

```sh
python -m pip install numpy==2.3.5
python scripts/build_air_heat_findings.py
python scripts/test_air_heat_findings.py
```

Use `python scripts/build_air_heat_findings.py --download-weather` only when
deliberately refreshing precipitation. Review its source metadata and resulting
changes before publishing. The numerical checks include independent regression
projection and calendar-aware covariance calculations, rainfall interval
boundaries and smoother fixtures. Hourly tests cover gaps, offsets, partial
endpoints and runs crossing midnight.
