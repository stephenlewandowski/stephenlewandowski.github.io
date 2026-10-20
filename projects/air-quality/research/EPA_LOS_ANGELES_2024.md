# Los Angeles hourly PM₂.₅, 2024

The comparison uses one continuous monitor at **Los Angeles–North Main Street**,
AQS **06-037-1103**, parameter **88101**, **POC 3**, **method 170**. The instrument
is a Met One BAM-1020 with VSCC; EPA identifies the hourly method as **FEM**.
This location represents one monitor, not average exposure across Los Angeles.

The measurements were downloaded on 20 October 2026 from
[EPA AirData's public hourly archive](https://aqs.epa.gov/aqsweb/airdata/hourly_88101_2024.zip).
No API key is required. The selected source has **8,624 distinct hourly rows**,
all from the same POC and method. No observations from other POCs are averaged
or substituted. Full source and extract hashes are in
`EPA_LOS_ANGELES_2024_AUDIT.json` and the prepared JSON's `sources` field.

The [EPA annual monitor archive](https://aqs.epa.gov/aqsweb/airdata/annual_conc_by_monitor_2024.zip)
marks this POC's 2024 **1 HOUR / Observed Values** summary **Certified**, with
8,624 observations, completeness indicator Y and Event Type “No Events.” This
is a verified source field, not a separate certification audit by this project.
Site and monitor metadata come from
[aqs_sites.zip](https://aqs.epa.gov/aqsweb/airdata/aqs_sites.zip) and
[aqs_monitors.zip](https://aqs.epa.gov/aqsweb/airdata/aqs_monitors.zip).

The source timestamps identify the **start of sampling**. Its local fields use
**PST, UTC−8, throughout the year**. Every selected row was checked against its
supplied GMT timestamp. The common comparison grid contains all 8,784 UTC-2024
hour slots. The eight hours at its beginning fall in the prior local year and
remain missing. A supplementary `localYear` array preserves the genuine local
2024 observations from 1 January 2024 08:00 UTC through 1 January 2025 07:00 UTC.
See [EPA's file format documentation](https://aqs.epa.gov/aqsweb/airdata/FileFormats.html).

The application consistently treats negative concentrations as missing. There
are **18 reported negative measurements** in this source; their original values
remain in the audit and compressed selected-row CSV. They are not replaced by
zero. Other missing hours remain null. This produces **8,598 valid UTC hours
(97.883%)** and **8,606 valid local-year hours**. The lowest monthly coverage is
April, **85.694%**; the lowest seasonal coverage is spring, **93.659%**.

There are **48 IH fireworks observations** and **one IT U.S. wildfire
observation**. Both are
[informational qualifiers in EPA's code table](https://aqs.epa.gov/aqsweb/documents/codetables/qualifiers.html),
so their measured values remain in the comparison. No selected record carries
a QA, null-data or request-exclusion qualifier. The annual “No Events” field
does not erase these informational flags. The extraction does not implement
EPA-concurred exceptional-event exclusions. The 4 July peak of **268.7 µg/m³**
is therefore preserved.

The data qualify for this project's seasonal comparison. They do **not**
reproduce the site's official regulatory design values: the separate daily FRM
**POC 1** is its NAAQS primary monitor. The current
[South Coast AQMD site survey](https://www.aqmd.gov/docs/default-source/clean-air-plans/air-quality-monitoring-network-plan/aaqmnp-losangeles.pdf?sfvrsn=16)
describes use of continuous POC 3 for annual comparison when manual values are
missing. Its current
[July 2026 comparability appendix](https://www.aqmd.gov/docs/default-source/clean-air-plans/air-quality-monitoring-network-plan/aaqmnp-appendix-cA4ED7731453B.pdf)
requests exclusion of **2025** POC 3 data after a 2023–2025 bias assessment. That
request does not establish exclusion of the 2024 series. The application uses
this hourly extract for descriptive and educational comparisons, with the
method limitation disclosed.

An independent Python Decimal calculation and the website's JavaScript module
agree on the cleaned local-year benchmark values: **360 valid days**, a
quarter-weighted annual mean of **13.468814 µg/m³**, an eighth-highest daily
value of **31.4 µg/m³**, and **five daily means above 35 µg/m³**. The annual mean
differs from EPA's published hourly arithmetic mean because the project applies
quarter weighting to daily values and excludes reported negative hours. The
daily percentile is a one-year statistic; it is not the three-year design value.

[EPA permits free reuse of its public-domain AQS monitoring data](https://www.epa.gov/outdoor-air-quality-data/do-i-need-request-permission-use-monitoring-data-and-graphics-airdata).

To reproduce the acquisition:

```powershell
python research/acquire_us_city_2024.py
```

The script uses Python's standard library and caches the nationwide archives in
the system temporary directory. Pass `--cache PATH` to reuse an existing cache,
or `--inventory` to inspect the candidate monitors without generating a new
comparison extract. It rejects changed row counts, methods, unexpected
qualifiers, inconsistent timestamps and duplicate source hours for review.

The original NYC candidate, CCNY 36-061-0135, was not selected because the
[NYSDEC 2024 network plan](https://dec.ny.gov/sites/default/files/2024-05/2024plan.pdf)
identifies its continuous instrument as non-FEM TEOM. EPA distinguishes
[parameter 88502 from the FRM/FEM/ARM stream 88101](https://www.epa.gov/aqs/aqs-memos-technical-note-reporting-pm25-continuous-monitoring-and-speciation-data-air-quality).
