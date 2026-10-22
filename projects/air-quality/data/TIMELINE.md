# PM₂.₅ record coverage, 2023–2025

The timeline extends the original 2024 comparison in both directions. The source
locations stay the same: Seoul's 25-district network, Pyeongtaek Songbuk-dong,
London HP1, Beijing OpenAQ location 8833 and Los Angeles North Main Street POC 3.
The additional years help test whether a pattern seen in 2024 recurs; three years
are still a short record for a long-term trend.

## Available years

The counts below use the common UTC calendar-year grid. A non-leap year has
8,760 possible hours. Local-year files preserve additional real observations
near UTC boundaries where the source supplies them.

| Location | 2023 valid UTC hours | 2024 | 2025 valid UTC hours |
| --- | ---: | --- | ---: |
| Seoul, fixed 25-district network | 8,740 (99.772%) | Original full-season baseline | 8,739 (99.760%) |
| Pyeongtaek, Songbuk-dong | 8,574 (97.877%) | Original full-season baseline; August outage | 8,521 (97.272%) |
| London, Honor Oak Park HP1 | 8,753 (99.920%) | Original full-season baseline | 8,653 (98.779%) |
| Beijing, OpenAQ 8833 | 7,019 (80.126%); winter/spring incomplete | Original full-season baseline | 1,470 (16.781%); January–early March only |
| Los Angeles, North Main Street POC 3 | 8,591 (98.071%) | Original full-season baseline | 8,376 (95.616%); see monitor comparability note below |

Seoul, Pyeongtaek, London and Los Angeles have observations in all seasons in the
new years. Beijing's 2023 winter and spring and its partial 2025 record fail the
75% every-season screen. These data remain available for covered-period analyses,
with gaps shown explicitly. Whole-year averages from these incomplete records
should not be ranked against complete-year means as though they sampled the same
seasons. Missing hours do not contribute to a below-threshold denominator.

## Korea

The original Seoul and Pyeongtaek sources each supply all 8,760 local hourly
labels in 2023 and 2025; individual measurements can still be missing. Their last
nine UTC calendar-year hours lie beyond the corresponding local-year archive
and remain null. The complete source local-year values are retained separately.

Seoul's local-year network capture is 99.874% in 2023 and 99.863% in 2025. It uses
the same fixed 25 monitors and requires 20 valid monitors per hour. This preserves
the geographic definition between years without filling district gaps. Individual
district completeness varies: Jung-gu's 2023 winter capture is 50.509%,
Eunpyeong-gu's 2025 winter capture 64.722%, and Gangseo-gu's 2025 spring capture
52.355%. Their district records carry seasonal completeness flags. The network
itself exceeds 99.6% capture in every season in both new local years.

Pyeongtaek's local-year capture is 97.979% in 2023 and 97.374% in 2025; all seasons
exceed 94%. Its raw provincial source reports 128 numeric zeros in 2023 and 229
in 2025, including consecutive runs of 21 and 16 hours. Zeros are retained as
reported, with no supplied per-reading QA flags or detection-limit explanation.
The 2024 August outage is specific to that year and is not copied into the new
years' metadata.

Seoul archives are municipal observations under KOGL Type 1. Pyeongtaek is the
provincial raw product, with unrestricted reuse documented in its official
government catalog; it is not substituted with the separately licensed national
final-confirmed archive. Original source hour labels and the existing possible
one-hour interval-convention uncertainty are preserved.

See [Korea source and preparation notes](../research/KOREA_MULTIYEAR.md) and the
[multi-year coverage and hash audit](../research/korea-multiyear-audit.json).

## London

The extension uses the same Honor Oak Park station (HP1) and annual LondonAir
RData product as 2024, on its original GMT timestamps. Annual capture is 99.920%
in 2023 and 98.779% in 2025, with every meteorological season above 95.3%. The
annual files embed no per-reading quality flags or separate ratification status;
the provider may revise measurements. The source documentation specifies Open
Government Licence v2 reuse.

## Beijing

The extension keeps OpenAQ location 8833 and PM₂.₅ sensor 25754. In 2023,
February capture is only 10.714% and March 49.194%; winter capture is 60.463%
and spring 65.036%, compared with summer 98.596% and autumn 96.154%. The last
valid 2023 reading is 28 December at 07:00 UTC.

The archived 2025 observations end on 4 March at 12:00 UTC. January capture is
99.866%, February 95.536% and March 11.425%; April through December remain
null. This is a source-availability limit, not evidence of low pollution later
in the year. A same-month comparison or analysis restricted to the actual
observations is possible; a full-year 2025 comparison is not.

## Los Angeles

The source remains EPA AQS site 06-037-1103, parameter 88101, continuous FEM method
170, POC 3. For 2023, 32 negative hourly readings are excluded under the common
nonnegative concentration rule; two informational fireworks hours remain. The
annual hourly summary is marked Certified. The local-year source retains 8,599
valid hours; eight fall before the UTC year and are not shifted or reassigned.

For 2025, South Coast AQMD's monitor bias assessment requests exclusion of this
POC 3 record from NAAQS comparisons. Retained hourly observations can support
exploratory plots and joint weather analyses, but they should not be interpreted
as a suitable regulatory record. The source has 8,376 valid UTC hours (95.616%)
and every season exceeds 93%; 27 negative readings are excluded. Informational
wildfire, fireworks, high-wind and construction flags remain attached to the
retained observations and are not treated as automatic exclusions. Certification, instrument comparability and
regulatory suitability are distinct questions. The site's primary daily FRM
monitor is POC 1; these extracts do not reproduce the official combined-site
design value.

See [global source and quality notes](../research/GLOBAL_PM_2023_2025.md) and
the city/year audits linked there for original URLs, qualifiers and hashes.

## Comparing years

Use the same location, month range, averaging method and coverage criteria when
comparing years. The plots and counts retain the actual gaps. A warmer season,
fire episode or monitor outage can change an annual mean independently of a
long-term change in air quality.

The U.S. standards panel reports a selected year's historical annual components
and daily counts. Having three years available does not by itself establish a
valid three-year regulatory design value. Site suitability, quarterly capture,
source qualifications and Appendix N requirements still apply; Seoul's network
average remains descriptive context.
