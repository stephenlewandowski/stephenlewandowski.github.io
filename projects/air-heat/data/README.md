# Pairing air-quality and weather records

This project reuses the retained 2024 records from the [air-quality comparison](../../air-quality/data/README.md)
and [heat-stress comparison](../../heat-stress/data/README.md). It does not download
new measurements when a visitor changes the controls. The [manifest](manifest.json)
links to those existing files, identifies their checksums and records independent
expected daily-pair counts. File paths in the manifest are relative to the
`projects/air-heat/` directory.

## What is being paired

The vertical axis is measured PM₂.₅ in µg/m³. The horizontal axis uses ERA5 weather
or an index calculated from that weather. These represent different spatial
supports: a pollution monitor or monitor network and a reanalysis grid point.
They are not measurements of one person's joint exposure.

| City | PM₂.₅ record | ERA5 grid point | Fixed local standard time |
| --- | --- | --- | --- |
| Seoul | Equal mean of available district monitors; at least 20 of 25 required per hour, or one selected district | 37.50° N, 127.00° E | UTC+9 |
| Pyeongtaek | Songbuk-dong, station 131344 | 37.00° N, 127.00° E | UTC+9 |
| London | Lewisham–Honor Oak Park, HP1 | 51.50° N, 0.25° W | UTC+0 |
| Beijing | AirNow/OpenAQ location 8833 | 40.00° N, 116.50° E | UTC+8 |
| Los Angeles | North Main Street, AQS 06-037-1103, POC 3 | 34.00° N, 118.25° W | UTC−8 |

The weather source is the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api),
explicitly selecting ERA5, the nearest model grid point and no elevation
adjustment. Its [CC BY 4.0 attribution](https://open-meteo.com/en/licence) and the
underlying ERA5 attribution remain applicable. The original PM providers are
Seoul Metropolitan Government, Gyeonggi Institute of Health and Environment,
London Air Quality Network/Imperial College London, AirNow through OpenAQ, and
U.S. EPA AirData/South Coast AQMD. Their source URLs, licences, retrieval metadata
and quality decisions are retained in the companion files and documentation.

All Seoul district choices use the **same Seoul weather grid**. Changing the
district changes the pollution record, not the weather estimate. The network
mean is an unweighted mean of reporting monitors, not a population-weighted city
exposure. The other cities use single pollution monitors.

## Daily means on shared hours

1. Join the two hourly records by their reported UTC timestamps. The arrays are
   not simply zipped: the Seoul district supplement begins nine hours before the
   common UTC-year records.
2. Group those timestamps into UTC days or fixed local standard-time days.
   Daylight saving time is not applied.
3. Keep only calendar days wholly inside both retained array extents and inside
   the selected 2024 calendar-date range. Endpoint fragments are excluded.
4. Identify hours when both PM₂.₅ and the selected weather measure are valid.
   At least **18 shared valid hours out of 24** are required.
5. Calculate both daily means from that same set of shared hours. An index is
   calculated hourly before averaging; it is not calculated from daily average
   weather inputs.

Missing and excluded estimates remain missing. Reported PM₂.₅ zeros remain
numeric values, and negative PM₂.₅ readings were already excluded by the source
preparation. Negative temperatures and UTCI values are valid. There is no gap
filling, sparse-day regulatory exception or additional EPA truncation.

The shared-hour rule matters when WBGT is selected. A daily PM₂.₅ mean paired with
WBGT may use fewer hours than the PM₂.₅ mean paired with temperature on that same
day. It is therefore a conditional mean of the hours when both measures were
available. Changing the weather measure can change both the eligible days and
their PM₂.₅ means; comparing regression fits without checking coverage can be
misleading.

The weather files cover 1 January 2024 00:00 through 31 December 2024 23:00 UTC.
They do not contain a padded local calendar year. For a nonzero local offset,
365 full local days fall within that archive; London has 366. The final UTC day
has only 15 reported Seoul/Pyeongtaek PM hours in the main UTC arrays because the
next Korean local-year source was not acquired. The ordinary completeness rule
still applies. The Seoul district supplement retains the original Korean local
year, but it cannot supply the weather hours missing before the UTC-year start.

## Coverage in the initial release

These counts use fixed local standard time, the full 2024 date selection, the
Seoul network mean and at least 18 shared hours. They are computed independently
by the Python audit, rather than copied from the interface.

| City | Complete calendar days | Temperature / UTCI paired days | Outdoor WBGT paired days | No-shortwave WBGT paired days |
| --- | ---: | ---: | ---: | ---: |
| Seoul | 365 | 365 | 204 | 202 |
| Pyeongtaek | 365 | 335 | 182 | 182 |
| London | 366 | 366 | 177 | 174 |
| Beijing | 365 | 351 | 183 | 182 |
| Los Angeles | 365 | 359 | 261 | 258 |

Temperature, relative humidity and UTCI have no missing weather hours in this
release, so their daily eligibility depends on the pollution record and complete
calendar days. WBGT omits many cold hours under the companion application's
conservative property-fit filter. Its missing values are neither zeros nor known
to be below a threshold, and its retained observations do not describe all
seasons equally. See the [full WBGT calculation and filter](../../heat-stress/data/README.md#wbgt-exposed-outdoors).

UTCI uses the companion application's **mean radiant temperature equal to air
temperature** scenario. It is not the radiation-inclusive ERA5-HEAT product. Its
polynomial method, wind floor and applicability limits are documented in the
[UTCI calculation notes](../../heat-stress/data/README.md#utci-no-added-radiant-heat).

## Source limitations that affect associations

- Seoul's source describes hourly means but does not explicitly identify
  hour-start versus hour-end semantics. Pyeongtaek's original 00–23 labels are
  preserved; a separate physical interval dictionary was not located. London
  uses GMT archive instants, Beijing uses its reported offset-aware UTC instants,
  and EPA defines Los Angeles timestamps as the start of sampling. Daily
  pairing preserves those labels; it does not establish exact physical overlap
  of every hourly sampling interval. A possible one-hour difference can also
  move observations across a calendar-day boundary.
- Pyeongtaek's August outage leaves only 15 eligible daily temperature/UTCI pairs
  out of 31 days. Its 644 source-reported zero PM₂.₅ hours remain included; the
  provincial archive provides no per-reading quality flags or detection-limit
  explanation for them. These issues can affect summer associations. See the
  [Pyeongtaek source audit](../../air-quality/research/PYEONGTAEK_2024.md).
- Los Angeles retains reported informational fireworks and wildfire observations
  and excludes 18 negative hourly values. Its hourly FEM POC 3 is not the site's
  primary daily regulatory monitor. Short episodes can strongly influence an
  ordinary least-squares fit. See the [Los Angeles source audit](../../air-quality/research/EPA_LOS_ANGELES_2024.md).
- The sources differ in monitoring method, spatial coverage and validation
  status. A common daily-pair rule makes the calculation consistent without
  removing those differences.

This is an exploration of environmental associations. It contains no individual
health outcomes, military cohort data or personal exposure history. A pollution
versus temperature regression does not estimate whether the joint exposures
interact in their effects on health. Seasonal patterns, meteorology, emissions,
transport and other unmeasured processes may contribute to the association.

## Reproduce the pairing audit

From the website repository root:

```powershell
python scripts/check_air_heat_data.py
```

The audit uses only the Python standard library. It verifies every linked source
checksum, input grid and value domain; independently rebuilds UTC and local
calendar-day pairs; checks per-month and per-season coverage; and verifies
alignment for all 25 Seoul district records. The manifest also records raw and
within-month Pearson correlations as numerical reference results for the
JavaScript analysis tests. Within-month correlations remove each calendar
month's mean from both measures; they are descriptive comparisons, not causal
adjustment for all seasonal or time-varying factors.

To save the full coverage report outside the website, append `--report PATH`.
After a deliberate companion-data update, review the changes before rebuilding
the provenance with `--update-manifest`. Checksums normalize CRLF to LF so Windows
checkouts agree with the source JSON bytes in Git and on the published website.
