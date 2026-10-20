# Heat stress in 2024

[Open the interactive comparison](https://stephenlewandowski.github.io/projects/heat-stress/).

Compare heat and humidity in Seoul, Pyeongtaek, London, Beijing and Los Angeles
through all seasons of 2024. The city set matches the
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
- Seasonal and time-of-day frequencies, exceedance curves,
  and a table comparing the measures for one city.

Each index is calculated **hourly before aggregation**. Relative humidity is in
percent; the other measures use degrees Celsius, but their scales are different.
UTCI and WBGT cannot be compared as interchangeable temperatures. WBGT shortcuts
are exploratory thresholds, not universal work/rest limits.

## Data and scope

The project archives 8,784 UTC hours per city from ERA5, retrieved through the
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
[manifest](data/manifest.json) for input provenance, calculation versions,
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
