---
layout: teaching-document
title: Surveillance and GIS for Public-Health Decisions
description: Lecture notes connecting surveillance purpose, data quality, geography, privacy, uncertainty, and action.
document_type: Lecture notes
material_title: Surveillance and GIS
material_path: /teaching/materials/surveillance-gis/
---

# Surveillance and GIS for Public-Health Decisions

**Audience:** Graduate or professional learners  
**Duration:** 45–60 minutes  
**Currentness:** Official-source baseline checked 2026-08-10; verify operational rules and datasets at point of use.

## Opening decision

A regional health office receives weekly reports of a fictional respiratory event from six service areas. Leadership must decide where to investigate reporting problems, where to examine a possible burden signal, and what can be shown publicly. The task is not to make a diagnosis from a map. It is to decide what the data can support now and what evidence should come next.

Ask learners to name four different statements: an observation, an interpretation, a causal claim, and an action. Keeping those categories separate is the module’s central discipline.

## Surveillance purpose and boundary with research

Public-health surveillance is organized around recurring collection, analysis, interpretation, and dissemination for prevention, control, response, or program improvement. Research seeks to develop or contribute to generalizable knowledge. The data source alone does not determine the category: purpose, design, intended use, and governance matter.

For the fictional exercise, identifying a reporting delay and deciding where to conduct follow-up are surveillance/program functions. Designing a study to estimate a generalizable exposure–response relationship would be research. This distinction does not replace an institution’s formal review process.

## From case definition to action

A surveillance count depends on an operational case definition, reporting opportunity, data flow, and analytic rule. Changing any component can change the apparent trend without changing underlying disease.

Use a five-part chain:

1. Define the event and eligible population.
2. Capture and transmit reports.
3. Check data quality and system performance.
4. Analyze by person, place, and time.
5. Communicate findings for a proportionate action.

Feedback matters: reporters are more likely to participate when the information returns in useful form.

## System and data-quality attributes

CDC’s foundational evaluation framework includes simplicity, flexibility, data quality, acceptability, sensitivity, predictive value positive, representativeness, timeliness, and stability. The objective determines which attributes matter most. A faster stream may be less complete; a highly specific definition may miss more events; additional variables may improve interpretation but reduce acceptability or timeliness.

Separate system sensitivity from clinical-test sensitivity. For a surveillance system, sensitivity may concern the proportion of target events detected or the capacity to detect outbreaks. Predictive value positive concerns how many detected/reported cases are true cases. Neither is inferable from a count alone.

For a quick data-quality audit, ask:

- Are required fields complete and plausible?
- Are delays similar across areas and weeks?
- Does the reporting network cover the target population?
- Did definitions, platforms, incentives, or staffing change?
- Is the system stable enough for the intended decision?

## Counts, rates, and denominators

Counts show workload and absolute burden. Rates put counts in relation to a population at risk:

`rate per 10,000 = reported events / population × 10,000`

The calculation is simple; the alignment is not. Numerator and denominator must describe compatible populations, geography, and time. A rate can be numerically correct yet substantively misleading when the denominator is stale, excludes people using a service, or does not match a changing boundary.

Small counts yield unstable rates. Suppression is missing information, not zero. Do not back-calculate suppressed values from totals or display combinations that defeat privacy protection.

## Geocoding and geographic units

Geocoding links an address to an actual or calculated coordinate and possibly to geographic areas. Address-range results may be interpolated, so positional uncertainty should be expected. Match status, unmatched records, benchmark/vintage, input quality, and permitted handling of addresses belong in the analytic record.

Points answer “where was this record located?” Areas answer “how were records summarized?” Common public-health units—counties, tracts, ZIP-related areas, service areas, or program-defined districts—serve different purposes. Administrative convenience does not guarantee epidemiologic relevance.

Coordinate/reference context and boundary vintage must match the workflow. A boundary product describes geography, not health. Health numerators and population denominators must be attached separately and checked for compatible years and units.

## Mapping counts and rates

A choropleth shades areas by a value. Shading raw counts often reproduces population size. Shading rates improves comparability but does not solve denominator error, small-number instability, or ecological inference.

Classification choices can create different visual stories. Equal intervals, quantiles, and meaningful thresholds can place the same area in different color classes. Show the legend, disclose the method, inspect the underlying distribution, and avoid implying sharp risk discontinuities at administrative boundaries.

## Scale, aggregation, and ecological inference

Changing scale can reveal or conceal patterns. Aggregating to larger units may stabilize rates and protect privacy but hide local variation. Finer units can improve targeting but increase instability, geocoding error, and disclosure risk.

An area with a high rate and an area-level characteristic does not prove that exposed individuals experienced the events. This is the ecological fallacy. A spatial pattern can guide verification, outreach, sampling, or study design; it does not by itself establish cause.

Spatial autocorrelation may make nearby observations more similar than distant ones, but a global or local statistic is optional at this stage. The first obligation is to understand data generation, denominator, scale, and measurement quality.

## Privacy, suppression, and communication

Maps can disclose through location, small cells, rare combinations, or repeated releases. Use the minimum geographic detail needed for the decision. Respect the data steward’s suppression and redistribution rules. State when values are suppressed and do not treat them as zero.

A defensible public message identifies:

- what was measured and during which period;
- whether the display shows counts or rates;
- the geographic unit and population denominator;
- important missingness, delay, or suppression;
- what the pattern does and does not establish;
- the next action and the evidence needed to revisit it.

## Applied synthesis

Return to the six fictional areas. Central has the largest count but not the highest rate. Riverbend has the highest displayed rate and weaker completeness. Southpoint is suppressed. A responsible recommendation might prioritize verification of Riverbend’s reporting process and denominator, examine the persistence of its pattern across time, and avoid a causal claim. Central may still require resources because absolute workload is highest.

Ask teams to finish three sentences:

1. “The data show…”
2. “The data do not establish…”
3. “We recommend next…”

The best response ties action intensity to evidence quality. Surveillance and GIS support professional judgment when they make uncertainty visible rather than hiding it.

## References

- CDC, [Updated Guidelines for Evaluating Public Health Surveillance Systems](https://www.cdc.gov/mmwr/preview/mmwrhtml/rr5013a1.htm).
- CDC, [Distinguishing Public Health Research and Public Health Nonresearch](https://www.cdc.gov/mmwr/preview/mmwrhtml/su6103a3.htm).
- CDC, [Describing Epidemiologic Data](https://www.cdc.gov/field-epi-manual/php/chapters/describing-epi-data.html).
- CDC, [Framework for Evaluating Large Health Care Data and Related Resources](https://www.cdc.gov/mmwr/volumes/73/su/su7303a1.htm).
- CDC, [CDC WONDER Frequently Asked Questions](https://wonder.cdc.gov/wonder/help/faq.html).
- U.S. Census Bureau, [2025 TIGER/Line Shapefiles](https://www.census.gov/geographies/mapping-files/2025/geo/tiger-line-file.html).
- U.S. Census Bureau, [Census Geocoder Documentation](https://www.census.gov/programs-surveys/geography/technical-documentation/complete-technical-documentation/census-geocoder.html).
