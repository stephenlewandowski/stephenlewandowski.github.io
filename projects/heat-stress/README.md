# Heat stress by city, 2023–2025

[Open the interactive comparison](https://stephenlewandowski.github.io/projects/heat-stress/).

Compare heat and humidity in Seoul, Pyeongtaek, London, Beijing and Los Angeles
through all seasons of 2023, 2024 and 2025. The city set matches the
[air-quality project](../air-quality/README.md), while using a consistent weather
reanalysis source for the heat comparison.

## What to compare

- Air temperature and relative humidity.
- UTCI with mean radiant temperature set equal to air temperature, explicitly
  labeled as a scenario with no added radiant heat.
- Physically modeled Liljegren outdoor WBGT and a separate scenario that removes
  shortwave radiation.
- Hourly values, daily means, daily maxima and minima, and trailing 8-hour and
  24-hour means.
- Hours and days at or above a chosen threshold, consecutive hot hours, and the
  differences between a high daily peak, mean and minimum.
- Full-year comparisons of means, percentiles, counts and shares above a threshold,
  with a year selector for exploring each archive and yearly CSV downloads.
- Seasonal and time-of-day frequencies, exceedance curves,
  and a table comparing the measures for one city.

Each index is calculated **hourly before aggregation**. Relative humidity is in
percent; the other measures use degrees Celsius, but their scales are different.
UTCI and WBGT cannot be compared as interchangeable temperatures. WBGT shortcuts
are exploratory thresholds, not universal work/rest limits.

## Data and scope

The project archives 26,304 UTC hours per city from ERA5: 8,760 in each of
2023 and 2025, and 8,784 in leap year 2024. Data are retrieved through the
Open-Meteo Historical Weather API. These are **gridded reanalysis estimates**,
not observations from the air-quality monitoring stations. Native nearest grid
cells are used without elevation adjustment. Visitors download local JSON and
need no API key.

Daily groups can follow UTC or fixed local standard time, without daylight
saving. The date selection always uses UTC. Partial days at the range boundaries
are omitted from daily statistics. Counts use greater than or equal to the
threshold and show valid-data denominators. Missing and out-of-domain values
remain gaps.
The count of dates with any qualifying hour retains known occurrences on
incomplete days; daily mean and minimum counts use complete eligible days.

This is a historical comparison. It does not reconstruct individual exposure,
indoor conditions or street-level shade. The UTCI scenario does not reproduce
full-sun UTCI; the WBGT estimates do not replace a workplace globe measurement.
WBGT hours that would extrapolate the model's evaporation property fit are
omitted. WBGT means therefore summarize eligible hours, with coverage shown,
rather than the full calendar year. This project filter is documented separately
from the UTCI validity limits.

See [data sources, assumptions and reproduction](data/README.md) and the
[year index](data/periods.json) and per-year manifests for input provenance, calculation versions,
grid coordinates and calculation coverage.

## Development

The application uses plain HTML, CSS and JavaScript modules. It reuses the
portfolio's air-quality presentation styles; its calculations are independent.

From the repository root:

```sh
node --test scripts/test_heat_stress.mjs
python scripts/check_heat_stress_data.py
python scripts/check_site.py
git diff --check
```

The offline fetch and build scripts are documented in the data README. Index
calculations use a pinned thermofeel release. Keep the source data, radiation
scenarios, valid-domain masks and units explicit when extending the project.

The 2024 record remains the default and its stored files are unchanged. Shared
views include `year=YYYY`; old 2024 links remain valid. Each year uses its actual
calendar and solar geometry. Three years support year-to-year comparisons, not
a long-term climate-trend estimate. Full-year summary percentages account for
leap-year length. WBGT coverage remains conditional on its property-fit filter.

## Heat-risk context

The interpretation section separates environmental hazard, personal exposure,
social vulnerability and health outcomes. It links to Lei et al. (2026),
[doi:10.1038/s43247-026-04137-z](https://doi.org/10.1038/s43247-026-04137-z),
as external research context. Full study title and journal are credited on the
page. Discovery credit is given to Ho Woo Nam's [DeBriefed, 16 October 2026](https://www.carbonbrief.org/debriefed-16-october-2026-nature-plans-insufficient-how-evs-saved-20bn-el-nino-and-uk-weather),
published by Carbon Brief. The study's 2000–2019 city assessment is separate
from this project's 2023–2025 inputs, definitions and calculations. Its data are
not joined to the five-city archive.

## Heat research guidance and attribution

The research-guidance section adds a short table about metric selection, temporal
and geographic support, and area versus population weighting. It links and credits:

- Gateway Exposome Coordinating Center (GECC), [Resource: Measuring Heat](https://gatewayexposome.org/resourcesanddata~measuring_heat).
- Emma L. Gause and colleagues (2026), *Data Considerations for Estimating Ambient Heat Exposure for Environmental Epidemiological Studies*, [doi:10.1007/s40572-026-00553-7](https://doi.org/10.1007/s40572-026-00553-7).
- Keith R. Spangler, Shixin Liang and Gregory A. Wellenius (2022), *Wet-Bulb Globe Temperature, Universal Thermal Climate Index, and Other Heat Metrics for US Counties, 2000–2020*, [doi:10.1038/s41597-022-01405-3](https://doi.org/10.1038/s41597-022-01405-3).

Discovery credit: [CAFE RCC](https://www.climatehealthcafe.org/), October 15,
2026 Health and Extreme Weather Community News. The explanation table is a
project synthesis, not a reproduction or endorsement by those sources.

The research context was checked October 25, 2026. The 2022 county descriptor
is cited for its documented period; the newer extended county release is not
ingested or represented as audited. This addition changes no weather data,
heat-index calculations, thresholds or health-outcome claims. Original weather,
software and algorithm credits remain in the data notes.
