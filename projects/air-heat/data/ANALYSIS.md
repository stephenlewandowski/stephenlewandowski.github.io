# Seasonal, weather and hourly analysis of 2024

This follow-up uses the five archived PM2.5 records and ERA5 grid cells described
in the [pairing notes](README.md). It adds precipitation from the same ERA5 grid
points through the public Open-Meteo archive. The [webpage](../index.html)
provides seasonal curves, model tables, approximate uncertainty intervals and
interactive counts of overlapping hourly conditions.

These are environmental concentration associations. The analysis contains no
health outcomes and cannot estimate physiological interaction, individual risk
or causal feedback between heat and pollution.

## Findings

The annual and within-month associations differ, but weather adjustment also
changes the within-month result. On a common sample of dates, Seoul's UTCI
coefficient falls from +0.603 to +0.132 micrograms/m3 per degree C after adding
wind, relative humidity and precipitation. Its partial R2 falls from 7.9% to
0.3%; the adjusted interval spans zero. Squared wind and humidity terms give
a similar estimate (+0.151). Much of the association is therefore shared with
other meteorological variation. This does not identify which atmospheric
process produced the pattern.

| City | Common dates | Weather-adjusted temperature coefficient | Weather-adjusted UTCI coefficient | UTCI lag 0–3 sum |
| --- | ---: | ---: | ---: | ---: |
| Seoul | 362 | 0.157 (−0.238 to 0.551) | 0.132 (−0.175 to 0.440) | −0.038 (−0.433 to 0.357) |
| Pyeongtaek | 296 | −0.156 (−0.572 to 0.259) | −0.082 (−0.397 to 0.233) | −0.288 (−0.723 to 0.146) |
| London | 363 | 0.262 (0.010 to 0.513) | 0.243 (0.044 to 0.443) | 0.266 (0.037 to 0.495) |
| Beijing | 334 | 2.487 (1.738 to 3.236) | 1.995 (1.373 to 2.616) | 1.526 (0.811 to 2.241) |
| Los Angeles | 350 | 0.666 (0.361 to 0.971) | 0.620 (0.356 to 0.884) | 0.559 (0.266 to 0.851) |

Coefficients are PM2.5 micrograms/m3 per 1 degree C. Parentheses are approximate
95% calendar-aware Newey–West intervals with a seven-day bandwidth. The lag sum
is the contrast for a 1 degree C higher thermal measure on **each** of today and
the three previous days, holding controls fixed. It is not the sum of pollution
over four days.

Beijing and Los Angeles retain positive associations with squared wind/humidity
terms and with prior-day PM2.5 included. The estimates become smaller after
conditioning on pollution persistence. London's current-day estimates weaken
under the squared-weather sensitivity, and its UTCI lag sum becomes +0.078
(−0.068 to 0.224) after adding prior-day PM2.5. Pyeongtaek's estimates are
sensitive to specification and incomplete coverage; its temperature lag-sum
interval crosses zero when the HAC bandwidth changes from seven to three days.
There is no single common thermal association across the five cities.

Seoul's unadjusted seasonal temperature smooth has a net rise from the 10th to
90th percentile in winter, declines in spring and autumn, and little change in
summer. These endpoint directions persist across the three smoothing spans.
The curves can bend between their endpoints and still contain monthly
progression within each season. They do not demonstrate an adjusted seasonal
dose response. Beijing's seasonal curves also differ, and Los Angeles has a
much flatter temperature curve in summer than spring.

Hourly pairing reveals overlap that daily thresholds can conceal. With reported
hourly PM2.5 at least 35 micrograms/m3 and temperature at least 30 degrees C:

| City | Valid paired hours | Hours meeting both | Days with any overlap | Longest observed run |
| --- | ---: | ---: | ---: | ---: |
| Seoul | 8,771 | 13 | 4 | 5 h |
| Pyeongtaek | 8,119 | 1 | 1 | 1 h |
| London | 8,775 | 0 | 0 | 0 h |
| Beijing | 8,435 | 358 | 60 | 14 h |
| Los Angeles | 8,598 | 2 | 2 | 1 h |

Using UTCI at least 32 degrees C instead yields 9, 0, 0, 233 and 0 overlapping
hours, respectively. Using temperature at most 0 degrees C yields 170, 183, 0,
626 and 0 hours. These are descriptive threshold choices. An hourly PM2.5 value
of 35 is **not** a U.S. hourly regulatory standard. Zero overlap can occur
because one threshold was rarely or never reached; it does not establish zero
joint health risk. Coverage, source quality and the chosen radiation scenario
also affect comparisons.

## Seasonal smooths

- Separate local linear LOESS fits for winter (January–February and December),
  spring (March–May), summer (June–August) and autumn (September–November).
- All eligible local-standard-time daily pairs are used, retaining the same
  at-least-18-shared-hours rule as the original application. Seoul uses the
  network mean. A seasonal curve is unadjusted for other weather variables.
- Tricube distance weights; the nearest `ceil(span * n)` observations set the
  distance bandwidth. Main span 0.65, with 0.50 and 0.80 sensitivity curves.
  There is no residual-based downweighting of pollution episodes.
- Curves are displayed only from each season's observed thermal 10th to 90th
  percentiles. Dashed sensitivity curves are **not confidence bands**. The
  remaining observations are still shown. Thermal ranges differ by season;
  the webpage uses a shared PM2.5 axis within a city/measure comparison.

See [NIST's LOESS description](https://www.itl.nist.gov/div898/handbook/pmd/section1/pmd144.htm).

## Weather inputs and timing

The retained heat files supply wind at 10 m in m/s and relative humidity in %.
Both current-day means use exactly the hours shared by PM2.5 and the selected
thermal measure. Temperature and UTCI have complete weather coverage in these
files, so the paired-hour masks agree for these two analyses.

[weather-2024.json](weather-2024.json) retains 8,808 hourly precipitation values
per city, from 2024-01-01 through 2025-01-01 UTC, with source URLs, grid
coordinates, retrieval times, units and raw-response hashes. The extra day
supplies the final midnight interval needed by the 2024 analysis. Requests pin
ERA5, the nearest grid cell and no elevation correction, matching the original
weather grids. Weather data retain the Open-Meteo/ERA5 attribution and
[CC BY 4.0 terms](https://open-meteo.com/en/licence).

Open-Meteo precipitation is the **sum over the preceding hour**, labeled by its
end. A local-day total therefore uses the 24 interval-end labels from local
01:00 through the next local 00:00. It is not a sum of labels 00:00–23:00.
These totals use all 24 precipitation intervals, rather than only valid PM
hours. See the [official interval definitions](https://open-meteo.com/en/docs/historical-weather-api).

The PM source interval conventions remain imperfectly documented. This
precipitation correction does not establish exact physical alignment among all
pollution and weather sampling intervals.

## Models and common sample

Models are fitted separately for each city and for temperature and UTCI.
All models within a city/measure use identical dates with eligible daily pairs
on that date and each of the previous three **calendar days**. Missing dates
are not bridged, and prior-day lag values use earlier calendar dates. This reduces the
samples from 365/335/366/351/359 daily pairs to 362/296/363/334/350 common dates.
Pyeongtaek's missing days thus have an amplified effect on the lag sample.

Let `Yt` be daily PM2.5, `Xt` the thermal measure, and `Mt` the month's intercept.
Let `Wt` contain current-day wind, relative humidity and `log(1 + daily rain)`.

1. Month differences: `Yt = Mt + b0 Xt + error`.
2. Weather adjustment: `Yt = Mt + b0 Xt + a Wt + error`.
3. Distributed lags: `Yt = Mt + sum(bj X[t−j], j=0..3) + a Wt + error`.
4. Prior-PM sensitivity: model 3 plus previous-day PM2.5.
5. Weather-form sensitivity: model 2 plus squared, mean-centered wind and
   relative humidity. The rain transformation stays unchanged.

The main controls are linear terms with a log transformation for precipitation;
the sensitivity is a limited check rather than exhaustive control for weather.
Lags 0–3, smoothing spans and HAC bandwidths were fixed for this follow-up.
They were not selected by searching for statistical significance. These remain
exploratory analyses of one year.

UTCI already incorporates wind and humidity. Its adjusted coefficient holds
those components fixed, and therefore differs from the overall association of
the index with pollution. UTCI still uses mean radiant temperature equal to air
temperature; this is not published ERA5-HEAT. Prior-day PM adjustment likewise
changes the question to an association conditional on pollution persistence.

Partial R2 is `1 − SSE(full model) / SSE(same-row controls-only model)`.
Controls-only excludes the thermal term or the block of four thermal terms.
It is not total model R2. The lag model has more thermal parameters, so a larger
partial R2 alone does not establish better prediction. Variance inflation is
reported after removing month differences. Correlated thermal lags can produce
alternating coefficients; individual lag signs do not identify mechanisms.

## Uncertainty and remaining dependence

The Newey–West sandwich uses Bartlett weights on the actual calendar-day
distances between regression score vectors. Gaps do not become adjacent days.
The covariance uses an `n/(n−p)` finite-sample correction and normal 1.96 intervals.
The main bandwidth is seven days; three and fourteen days are sensitivity checks.
The full coefficient covariance is used for the lag-sum interval, including
cross-lag covariances. These are approximate coefficient intervals, not
prediction intervals or health-effect estimates.

Residual lag-1 correlation counts only consecutive calendar dates. Adding
prior-day PM substantially reduces residual dependence, but some remains,
especially in Beijing. HAC addresses uncertainty under temporal dependence;
it does not correct omitted-variable bias, exposure error, the one-year sample
or uncertainty about the chosen model forms. The analysis has no held-out
forecast validation. See the [environmental time-series tutorial](https://academic.oup.com/ije/article/42/4/1187/657875).

## Hourly duration

The interactive hourly analysis follows the upper controls, including dates,
season, calendar, city and Seoul monitor. It joins reported UTC hourly labels
and requires finite PM2.5 at least zero and a finite thermal value. It retains
partial boundary dates, reports their coverage and does not impose daily
18-hour capture. Counts include equality at the selected thresholds.

A run comprises consecutive selected hourly labels satisfying both conditions.
Midnight does not interrupt a run. Missing values, unselected hours and hours
failing either condition interrupt it. Missing observations are not below
threshold. Runs touching a missing hour, archive edge or selection boundary
receive a boundary flag because continuation is unknown. The observed length
is a count of hourly labels, not a verified personal exposure duration. Monthly
counts allocate each hour to its own calendar month even when a run crosses
midnight or the end of a month.

## Reproduce and check

The website serves the retained results without a visitor API request. The
builder requires Python and NumPy; the browser has no statistical dependency.

```sh
python -m pip install numpy==2.3.5
python scripts/build_air_heat_findings.py
python scripts/test_air_heat_findings.py
node --test scripts/test_air_heat.mjs scripts/test_air_heat_hourly.mjs
python scripts/check_air_heat_data.py
python scripts/check_site.py
```

The ordinary builder uses retained inputs offline. `--download-weather` explicitly
refreshes precipitation from the public archive before rebuilding. Review any
source change before replacing published results. Source SHA-256 values in
[findings.json](findings.json) normalize CRLF to LF.

Checks independently verify timestamp alignment, precipitation interval
boundaries, regression coefficients through residual projection, LOESS line and
tie fixtures, and calendar-aware HAC against an exhaustive double-sum reference.
An independent SVD/kernel audit also checked the 20 main weather and lag models.
Hourly tests cover missing observations, midnight continuity, censoring,
partial endpoints, offsets and seasonal boundaries. Fifteen real-data hourly
summaries also agreed with an independent timestamp-map calculation.
