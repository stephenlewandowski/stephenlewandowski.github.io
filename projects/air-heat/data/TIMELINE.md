# Air pollution and thermal conditions, 2023–2025

The daily and hourly explorer now spans 2023, 2024 and 2025. Each year has a
separate source manifest, actual calendar grid and data-completeness audit.
Select a year at the top; old links without a year still open 2024. The yearly
comparison table uses each full archived local standard-time year, independently
of the shorter date/season/district selections. Seoul uses its network mean in
that table and the advanced models.

The [PM timeline notes](../../air-quality/data/TIMELINE.md) describe original
provider access, monitoring locations and quality caveats. All five cities have
complete ERA5 weather in all three years. The PM records have different gaps:

| City | Daily temperature/UTCI pairs, 2023 | 2024 | 2025 |
| --- | ---: | ---: | ---: |
| Seoul | 364 | 365 | 364 |
| Pyeongtaek | 356 | 335 | 355 |
| London | 365 | 366 | 359 |
| Beijing | 286 | 351 | 60 |
| Los Angeles | 359 | 359 | 347 |

Pairing requires at least 18 shared valid hours and a complete calendar day
within both source arrays. Nonzero time offsets omit partial endpoint dates.
Weather has 8,760 UTC hours in 2023/2025 and 8,784 in leap-year 2024. Index-specific
WBGT availability is smaller; the comparison table checks coverage for the
selected metric, rather than borrowing temperature completeness.

Beijing's 2023 winter/spring gaps and January–early March-only 2025 record remain
available for daily/hourly exploration. They fail the 75% paired-day screen in
at least one season, so those city-years are omitted from full-year advanced
models. Seasonal coverage is assessed against possible calendar days, including
days whose pollution observations are all missing.

## What the added years show

Seoul's annual temperature–PM2.5 correlation is negative in each year, while
its within-month correlation is positive. The reversal observed in 2024 recurs
on both sides of that year:

| Seoul | 2023 | 2024 | 2025 |
| --- | ---: | ---: | ---: |
| Annual temperature correlation | −0.262 | −0.259 | −0.282 |
| Within-month temperature correlation | +0.188 | +0.140 | +0.260 |
| Within-month UTCI correlation | +0.308 | +0.285 | +0.395 |
| Weather-adjusted UTCI coefficient | 0.314 | 0.132 | 0.347 |
| Approximate 95% HAC interval | 0.019 to 0.608 | −0.175 to 0.440 | 0.008 to 0.687 |
| UTCI lag 0–3 sum | 0.159 | −0.038 | 0.114 |
| Approximate 95% HAC interval for lag sum | −0.163 to 0.481 | −0.433 to 0.357 | −0.253 to 0.480 |

Coefficients are micrograms/m3 per 1 degree C. Same-day weather-adjusted UTCI
point estimates are positive in all three years, but their sizes and uncertainty
differ. The lag sums all have intervals spanning zero. A consistent raw or
within-month direction therefore does not imply one stable, independent thermal
association. These are separately fitted exploratory estimates; comparing their
intervals is not a formal test of year-by-year effect differences.

Pyeongtaek also has negative annual and positive within-month temperature
correlations in all three years. London is less consistent: its within-month
temperature correlation is −0.113, +0.108 and +0.032 in 2023/2024/2025, although
within-month UTCI correlations remain positive. Los Angeles has positive
within-month temperature correlations each year, even though its 2025 annual
correlation is nearly zero. This reinforces the importance of time scale and
meteorology when comparing the records.

Los Angeles retains positive weather-adjusted coefficients in the added years.
Its 2025 source retains informational wildfire, fireworks, high-wind and
construction flags. The provider requests exclusion of that year's POC 3 data
from NAAQS comparison; the PM application's U.S. reference panel respects that
request. Environmental exploration remains available. Larger 2025 coefficients
must be interpreted with those source qualifications and episode influences in
mind; they do not establish a changed atmospheric mechanism.

Three years reveal interannual variation but remain too short to establish a
long-term trend. The annual UTC-hour PM2.5 mean in Seoul is 19.63, 17.53 and
18.49 micrograms/m3. The decrease into 2024 does not continue into 2025. Beijing's
partial-year means cannot be compared with full-year means as though they sampled
the same seasons. Missing hours are never imputed or counted as below threshold.

## Advanced models and hourly duration

The [original analysis notes](ANALYSIS.md) document the model equations and 2024
findings. The same specified models are now fitted separately to each eligible
2023 and 2025 city-year: month intercepts, current weather, simultaneous thermal
lags 0–3, prior-PM sensitivity and squared-weather sensitivity. Every specification
within a city/year/measure uses the same lag-complete rows. The uncertainty
calculation uses actual calendar-day distances, with HAC bandwidth 7 and
sensitivities 3/14. Partial R2 and lag-sum interpretations remain unchanged.

Precipitation is separately archived for each year, including one extra UTC day
to supply the last midnight interval. Totals use the preceding-hour interval ends
from local 01:00 through the following local 00:00. UTCI remains the scenario
with mean radiant temperature equal to air temperature, not published ERA5-HEAT.
Weather adjustment of UTCI conditions on wind and humidity components of the index.

Hourly counts, consecutive runs, threshold directions, gap interruptions and
censoring operate on the selected year. Runs do not continue across a year boundary
because years are loaded separately; boundary flags identify that truncation.
An hourly PM2.5 threshold is a descriptive reference, not a federal hourly standard
or a health-risk boundary. There are no health outcomes in these data.

## Reproduce

```sh
python scripts/build_environment_timeline.py
python scripts/build_air_heat_findings.py --year 2023
python scripts/build_air_heat_findings.py --year 2025
python scripts/check_air_heat_timeline_models.py
node --test scripts/test_environment_timeline.mjs
```

The timeline builder uses retained sources only. The findings builder requires
NumPy 2.3.5 and retained precipitation. Add `--download-weather` deliberately to
refresh precipitation from the public ERA5 archive. Rebuilding a source requires
reviewing the affected provenance and findings before publication.

[2023 source manifest](manifest-2023.json) · [2024 manifest](manifest.json) ·
[2025 manifest](manifest-2025.json) · [yearly comparison data](timeline-summary.json) ·
[2023 models](findings-2023.json) · [2024 models](findings.json) ·
[2025 models](findings-2025.json)
