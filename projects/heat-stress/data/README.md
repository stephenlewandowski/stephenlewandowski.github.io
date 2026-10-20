# Weather data and heat-index calculations

The comparison covers all 8,784 UTC hours of 2024 for Seoul, Pyeongtaek, London,
Beijing and Los Angeles. These are **ERA5 reanalysis grid estimates**, accessed
through the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api).
They are not readings from the air-quality monitors or from local WBGT instruments.

The requests select `models=era5`, `cell_selection=nearest` and `elevation=nan`.
This keeps one model source and disables Open-Meteo's elevation adjustment.

| City | Requested latitude, longitude | Returned ERA5 grid point | Grid elevation | Local standard-time offset |
| --- | --- | --- | --- | --- |
| Seoul | 37.5665, 126.9780 | 37.50, 127.00 | 88 m | UTC+9 |
| Pyeongtaek | 37.0159, 127.1172 | 37.00, 127.00 | 65 m | UTC+9 |
| London | 51.5074, −0.1278 | 51.50, −0.25 | 71 m | UTC+0 |
| Beijing | 39.9042, 116.4074 | 40.00, 116.50 | 22 m | UTC+8 |
| Los Angeles | 34.0522, −118.2437 | 34.00, −118.25 | 134 m | UTC−8 |

Grid estimates describe the broader weather around each location. They do not
resolve the temperature of an individual street, courtyard or workplace.

## Retained files

[manifest.json](manifest.json) identifies each city file and its SHA-256 hash,
software versions, methods, calculation diagnostics and references. Each city
record includes the requested location, returned grid location, exact source URL,
retrieval time and raw-response hash.

The `values` object contains hourly `temperature`, `humidity`, `utci`, `wbgt` and
`wbgtShade` arrays on the same UTC time grid. Index 0 is 2024-01-01 00:00 UTC;
subsequent indices advance by one hour. Temperature indices use °C; humidity uses
percent. Missing or excluded estimates are `null`, never zero. This release has
no missing weather inputs or UTCI estimates. The WBGT calculations exclude hours
outside the application's property-fit filter described below.

The `inputs` object also retains dew point (°C), 10 m wind (m/s), surface pressure
(hPa), global horizontal shortwave radiation (W/m²) and direct horizontal
radiation (W/m²). The radiation arrays are Open-Meteo's `*_instant` estimates for
the indicated timestamp, derived from its hourly data. They are not instantaneous
instrument observations. The acquisition archive keeps the original responses,
including preceding-hour radiation averages and additional radiation components.

Values are stored to 0.1 unit. The application calculates counts, averages and
percentiles from these retained hourly values; values close to a threshold can
therefore be affected by rounding. The thermal indices are calculated **before**
any temporal aggregation. Calculating an index from an annual mean temperature
and humidity would produce a different result.

Local standard time uses the fixed offsets above, without daylight saving time.
The retained period is a full UTC year, not a padded local calendar year. Local
days touching the archive endpoints can therefore be partial; the application's
daily completeness rule applies to them as well.

## UTCI: no added radiant heat

UTCI combines air temperature, humidity, 10 m wind and mean radiant temperature.
This version sets **mean radiant temperature equal to air temperature**. It is a
controlled radiation assumption, not an estimate of each city's actual shade or
full-sun UTCI. Open-Meteo does not provide the complete longwave radiation inputs
needed to reconstruct the [ERA5-HEAT](https://cds.climate.copernicus.eu/datasets/derived-utci-historical?tab=overview)
mean radiant temperature. That dataset is a possible future extension.

The [Bröde et al. operational polynomial](https://doi.org/10.1007/s00484-011-0454-1)
is evaluated with [thermofeel 2.3.0](https://github.com/ecmwf/thermofeel/blob/2.3.0/thermofeel/thermofeel.py).
Wind below 0.5 m/s is raised to 0.5 m/s. Values outside the remaining applicability
limits—air temperature −50 to +50 °C, 10 m wind up to 17 m/s, vapour pressure up to
50 hPa and RH from 0 to 100%—are omitted. With MRT equal to air temperature, its
permitted difference of −30 to +70 °C is satisfied automatically.

| City | Hours with UTCI wind raised to 0.5 m/s | Hours omitted outside the domain |
| --- | --- | --- |
| Seoul | 188 | 0 |
| Pyeongtaek | 202 | 0 |
| London | 51 | 0 |
| Beijing | 378 | 0 |
| Los Angeles | 581 | 0 |

UTCI heat categories use thresholds of 26, 32, 38 and 46 °C: moderate, strong,
very strong and extreme heat stress, respectively. These refer to the UTCI
reference person and environment. They are not personal medical assessments or
workplace exposure limits. See the [ECMWF description of UTCI](https://confluence.ecmwf.int/spaces/CKB/pages/462912535).

## WBGT: exposed outdoors

The [Liljegren et al. model](https://doi.org/10.1080/15459620802310770) solves
energy balances for a natural wet-bulb sensor and a globe sensor. The
[pinned implementation](https://github.com/ecmwf/thermofeel/blob/2.3.0/thermofeel/liljegren.py)
combines them as `0.7 × natural wet-bulb + 0.2 × globe + 0.1 × air temperature`.
It uses humidity, pressure, wind and solar radiation; this is not the simple
temperature-and-humidity WBGT approximation.

Global and direct horizontal instantaneous-time radiation estimates are paired
with [earthkit-meteo solar geometry](https://earthkit-meteo.readthedocs.io/en/stable/autoapi/earthkit/meteo/solar/index.html)
at each UTC timestamp and returned grid point. Direct horizontal divided by
global horizontal radiation supplies the direct-beam fraction. The model's
default wind profile converts 10 m wind to the 2 m sensor height. Its 10 m wind
floor is 0.62 m/s; direct-beam and low-sun guards are retained.

This reconstruction keeps the model's assumed clear-sky atmospheric emissivity,
surface temperature equal to air temperature, surface albedo 0.45 and surface
emissivity 0.999. It does not recreate nearby buildings, cloud-dependent
longwave radiation, hot pavement or a particular person's exposure. No solver
failed to converge in this release. WBGT is not used as a cold-stress index.

The app applies a conservative filter to avoid extending a model property fit
into cold weather. The implementation's latent-heat helper documents a range of
**283 to 313 K**, evaluated at the mean of air and natural wet-bulb temperature.
If that converged mean falls outside the range, the app omits the hourly WBGT.
This is an application policy tied to that property fit, **not a published
validity range for the whole WBGT model** or an air-temperature cutoff. Each
radiation scenario is filtered using its own natural wet-bulb temperature.

| City | Exposed-outdoors hours retained | No-shortwave hours retained |
| --- | --- | --- |
| Seoul | 5,358 / 8,784 | 5,292 / 8,784 |
| Pyeongtaek | 5,479 / 8,784 | 5,394 / 8,784 |
| London | 5,077 / 8,784 | 4,940 / 8,784 |
| Beijing | 5,112 / 8,784 | 4,997 / 8,784 |
| Los Angeles | 7,612 / 8,784 | 7,558 / 8,784 |

WBGT averages and percentages therefore describe **retained hours**, rather
than the entire selected period. Their weather conditions differ by city and
scenario; an annual mean is not a comparison over identical weather coverage.
Excluded hours are neither zero nor known to be below a threshold. Counts show
the exceedances found among retained hours. Temperature, humidity and UTCI
remain available for every hour, including winter.

## WBGT: no shortwave radiation

This scenario removes all shortwave radiation at the sensors while retaining
the same ambient wind profile and longwave assumptions. The no-solar-load
weighting is `0.7 × natural wet-bulb + 0.3 × globe temperature`, following the
[WBGT solar/no-solar formulation](https://pythermalcomfort.readthedocs.io/en/stable/_modules/pythermalcomfort/models/wbgt.html).
It helps explore the effect of the radiation assumption. It does not establish
the WBGT beneath a real tree, shade structure or indoor roof.

WBGT interpretation depends on workload, clothing and acclimatization. The
application's selected thresholds are comparison settings,
not a work/rest prescription or compliance determination. The
[National Weather Service explanation](https://www.weather.gov/sgf/wbgt)
describes why WBGT differs from air temperature and the heat index.

## Reproduce

Use Python 3.11 or later in a dedicated virtual environment. From the repository
root:

```powershell
python -m pip install -r scripts/requirements_heat_stress.txt
python scripts/fetch_heat_stress_data.py
python scripts/build_heat_stress_data.py
python scripts/build_heat_stress_data.py --validate-only
python scripts/check_heat_stress_data.py
```

The fetcher retains the raw responses and provenance in the sibling
`heat-stress-comparison/research/` directory by default. Both scripts accept
explicit source/output locations; use `--help` for their options. The builder
also accepts `--dependency-dir` for a task-local `pip --target` installation.
It makes no network calls and checks source hashes and every hourly timestamp.

Before building, the script checks an independently documented UTCI example
(25 °C air/MRT, 50% RH and 1 m/s wind → 24.6 °C) and the pinned upstream
[UTCI and Liljegren WBGT reference cases](https://github.com/ecmwf/thermofeel/tree/2.3.0/tests).
The published JSON and its hashes use UTF-8 with LF line endings, including on
Windows.

## Attribution

Weather data: [Open-Meteo](https://open-meteo.com/) and
[Copernicus/ECMWF ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview).
Open-Meteo data are redistributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
as described in its [licence](https://open-meteo.com/en/licence). Changes include
city selection, heat-index calculations, rounding and temporal summaries.
The published app serves the archived JSON locally and does not call the API.
Calculation software is credited in the manifest and pinned in the build
requirements; thermofeel and earthkit-meteo use Apache-2.0 licences.
