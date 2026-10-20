"""Acquire a 2024 Los Angeles hourly PM2.5 monitor from EPA AirData (no key).

Uses only Python's standard library. The nationwide archives are cached in the
system temporary directory. Run --inventory to inspect candidate POCs/methods
before preparing the selected series. A single POC is retained throughout; no
collocated monitor averaging, interpolated values, or invented boundary hours.
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import urllib.request
import zipfile

BASE = Path(__file__).resolve().parents[1]
CACHE = Path(tempfile.gettempdir()) / "air-quality-2024-epa"
OUT = BASE / "data" / "comparisons"
AIRDATA = "https://aqs.epa.gov/aqsweb/airdata/"
FILES = ["hourly_88101_2024.zip", "annual_conc_by_monitor_2024.zip", "aqs_sites.zip", "aqs_monitors.zip"]
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
HOURS = 8784
CANDIDATES = {("36", "061", "0135"): "NYC CCNY", ("06", "037", "1103"): "Los Angeles North Main Street"}
LA = ("06", "037", "1103")
DOCS = {
    "fileFormats": AIRDATA + "FileFormats.html",
    "qualifiers": "https://aqs.epa.gov/aqsweb/documents/codetables/qualifiers.html",
    "methodAdvisory": AIRDATA + "Data_Advisory_PM25_88101_Pregen_Files.pdf",
    "siteSurvey": "https://www.aqmd.gov/docs/default-source/clean-air-plans/air-quality-monitoring-network-plan/aaqmnp-losangeles.pdf?sfvrsn=16",
    "comparability": "https://www.aqmd.gov/docs/default-source/clean-air-plans/air-quality-monitoring-network-plan/aaqmnp-appendix-cA4ED7731453B.pdf",
    "reuse": "https://www.epa.gov/outdoor-air-quality-data/do-i-need-request-permission-use-monitoring-data-and-graphics-airdata",
}


def fetch(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    url = AIRDATA + name
    if not path.exists():
        temporary = path.with_suffix(".download")
        request = urllib.request.Request(url, headers={"User-Agent": "HistoricalAirQualityComparison/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as target:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
        temporary.replace(path)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, f"Corrupted source: {path}"
    return name, {"url": url, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "bytes": path.stat().st_size,
                  "downloadedAtUtc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}


def read_candidates(name):
    """Filter lines before CSV parsing to keep the 8-million-row file inexpensive."""
    prefixes = tuple(','.join(f'"{part}"' for part in code) + ',' for code in CANDIDATES)
    plain_prefixes = tuple(','.join(code) + ',' for code in CANDIDATES)
    with zipfile.ZipFile(CACHE / name) as archive:
        member = next(item for item in archive.namelist() if item.lower().endswith(".csv"))
        with archive.open(member) as zipped, io.TextIOWrapper(zipped, encoding="utf-8-sig", newline="") as text:
            header = next(text)
            selected = [line for line in text if line.startswith(prefixes + plain_prefixes)]
    return list(csv.DictReader(io.StringIO(header + ''.join(selected))))


def inventory(datasets):
    hourly = datasets["hourly_88101_2024.zip"]
    groups = defaultdict(list)
    for row in hourly:
        key = (row['State Code'], row['County Code'], row['Site Num'], row['POC'], row['Method Code'], row['Method Name'])
        groups[key].append(row)
    output = {"hourly": [{"key": key, "rows": len(rows),
        "qualifiers": dict(Counter(row['Qualifier'] for row in rows)),
        "methodTypes": dict(Counter(row['Method Type'] for row in rows)),
        "firstLocal": min(row['Date Local'] + ' ' + row['Time Local'] for row in rows),
        "lastLocal": max(row['Date Local'] + ' ' + row['Time Local'] for row in rows),
        "negative": sum(float(row['Sample Measurement']) < 0 for row in rows if row['Sample Measurement'])}
        for key, rows in groups.items()],
        "annual": datasets["annual_conc_by_monitor_2024.zip"],
        "sites": datasets["aqs_sites.zip"], "monitors": datasets["aqs_monitors.zip"]}
    return output


def is_la(row):
    return (row['State Code'], row['County Code'], row.get('Site Num', row.get('Site Number'))) == LA


def capture(values):
    months = []
    first = 0
    for month in range(1, 13):
        expected = calendar.monthrange(2024, month)[1] * 24
        valid = sum(value is not None for value in values[first:first + expected])
        months.append({"month": month, "expectedHours": expected, "validHours": valid,
                       "capturePercent": round(100 * valid / expected, 3)})
        first += expected
    return months


def seasonal_capture(values):
    groups = {"Winter (Jan–Feb, Dec)": [], "Spring (Mar–May)": [],
              "Summer (Jun–Aug)": [], "Autumn (Sep–Nov)": []}
    for hour, value in enumerate(values):
        month = (START + timedelta(hours=hour)).month
        label = "Winter (Jan–Feb, Dec)" if month in (1, 2, 12) else "Spring (Mar–May)" if month <= 5 else "Summer (Jun–Aug)" if month <= 8 else "Autumn (Sep–Nov)"
        groups[label].append(value)
    return {name: {"expectedHours": len(items), "validHours": sum(value is not None for value in items),
                   "capturePercent": round(100 * sum(value is not None for value in items) / len(items), 3)}
            for name, items in groups.items()}


def prepare(datasets, provenance):
    selected = [row for row in datasets['hourly_88101_2024.zip'] if is_la(row)
                and row['Parameter Code'] == '88101' and row['POC'] == '3']
    assert len(selected) == 8624, "Re-audit changed EPA source before publishing"
    assert {row['Method Code'] for row in selected} == {'170'}
    assert {row['Method Type'] for row in selected} == {'FEM'}
    assert {row['Units of Measure'] for row in selected} == {'Micrograms/cubic meter (LC)'}
    assert {row['Qualifier'] for row in selected} <= {'', 'IH', 'IT'}, "Review any new qualifier before use"
    annual = [row for row in datasets['annual_conc_by_monitor_2024.zip'] if is_la(row)
              and row['Parameter Code'] == '88101' and row['POC'] == '3' and row['Sample Duration'] == '1 HOUR']
    assert len(annual) == 1
    assert int(annual[0]['Observation Count']) == len(selected)
    sites = [row for row in datasets['aqs_sites.zip'] if is_la(row)]
    monitors = [row for row in datasets['aqs_monitors.zip'] if is_la(row) and row['Parameter Code'] == '88101']
    assert len(sites) == 1 and sites[0]['GMT Offset'] == '-8'
    local_start = START + timedelta(hours=8)
    values = [None] * HOURS
    local_values = [None] * HOURS
    timestamps = set()
    flagged, negatives = [], []
    out_of_utc = 0
    for row in selected:
        utc = datetime.fromisoformat(row['Date GMT'] + 'T' + row['Time GMT']).replace(tzinfo=timezone.utc)
        local_clock = datetime.fromisoformat(row['Date Local'] + 'T' + row['Time Local']).replace(tzinfo=timezone.utc)
        assert utc == local_clock + timedelta(hours=8), "Unexpected local/UTC convention"
        assert utc.minute == 0 and utc.second == 0
        assert utc not in timestamps, "Do not average duplicate source hours"
        timestamps.add(utc)
        value = float(row['Sample Measurement'])
        assert math.isfinite(value)
        utc_index = int((utc - START).total_seconds() / 3600)
        local_index = int((utc - local_start).total_seconds() / 3600)
        assert 0 <= local_index < HOURS
        detail = {"utc": utc.isoformat().replace('+00:00', 'Z'),
                  "local": row['Date Local'] + 'T' + row['Time Local'],
                  "value": value, "qualifier": row['Qualifier'], "methodCode": row['Method Code']}
        if row['Qualifier']:
            flagged.append(detail)
        if value < 0:
            negatives.append(detail)
        else:
            local_values[local_index] = value
            if 0 <= utc_index < HOURS:
                values[utc_index] = value
        if not 0 <= utc_index < HOURS:
            out_of_utc += 1
    valid = [value for value in values if value is not None]
    months = capture(values)
    seasons = seasonal_capture(values)
    assert len(values) == HOURS and len(local_values) == HOURS
    assert len(valid) / HOURS >= .75
    assert all(season['capturePercent'] >= 75 for season in seasons.values())
    gap = longest_gap = 0
    for value in values:
        gap = gap + 1 if value is None else 0
        longest_gap = max(longest_gap, gap)
    qa_status = ("EPA's 2024 annual summary marks this hourly POC 3 series Certified. "
                 "The comparison excludes 18 reported negative hourly values under its consistent nonnegative rule "
                 "and retains informational fireworks/wildfire observations. The site's daily FRM POC 1 is primary; "
                 "these hourly FEM benchmarks are educational comparisons, not official site design values.")
    event_note = ("Retain 48 IH fireworks hours and one IT U.S. wildfire hour: EPA classifies both codes as informational. "
                  "No request-exclusion, null-data or QA qualifier appears in the selected hourly records. "
                  "The annual hourly summary reports Event Type 'No Events'; this denotes no exclusion-event partition, "
                  "not an absence of informational source flags. No EPA event-exclusion claim is made.")
    regulatory_note = ("The site's daily FRM POC 1 is its NAAQS primary monitor. The current South Coast AQMD survey "
                       "permits use of hourly POC 3 for annual comparisons when manual observations are missing. "
                       "The current July 2026 comparability appendix requests exclusion of POC 3's 2025 data after "
                       "a 2023–2025 bias assessment; it does not establish an exclusion of this 2024 series. "
                       "This extract neither combines collocated monitors nor reproduces official site design values.")
    record = {"schemaVersion": 1, "id": "los-angeles", "city": "Los Angeles", "label": "Los Angeles · North Main Street", "year": 2024,
        "pollutant": "PM2.5", "units": "µg/m³", "timeZone": "America/Los_Angeles", "standardOffsetMinutes": -480,
        "station": {"id": "06-037-1103", "name": "Los Angeles – North Main Street",
            "provider": "South Coast Air Quality Management District / US EPA AirData",
            "type": "Single continuous FEM monitoring location; BAM-1020 with VSCC",
            "latitude": float(sites[0]['Latitude']), "longitude": float(sites[0]['Longitude']),
            "url": DOCS['siteSurvey'], "parameterCode": "88101", "poc": 3, "methodCode": "170", "methodType": "FEM"},
        "startUtc": "2024-01-01T00:00:00Z", "intervalMinutes": 60,
        "periodBasis": "UTC calendar year; the genuine local-standard 2024 source year is additionally retained in localYear",
        "timeConvention": {"source_timezone": "America/Los_Angeles", "source_utc_offset_minutes": -480,
            "source_label_field": "Date Local + Time Local; Date GMT + Time GMT",
            "hour_interval_semantics": "EPA defines hourly timestamps as the beginning of sampling; local fields use fixed local standard time (PST, UTC−8), not daylight-saving time.",
            "utc_conversion": "Use the supplied Date GMT + Time GMT directly; verified against every local timestamp plus 8 hours.",
            "source_first_local_label": "2024-01-01T00:00", "source_last_local_label": "2024-12-31T23:00",
            "documentation": DOCS['fileFormats']},
        "values": values, "localYear": {"startUtc": "2024-01-01T08:00:00Z", "intervalMinutes": 60,
            "timeBasis": "PST fixed local standard time, midnight through midnight, 2024 calendar year",
            "values": local_values, "expectedHours": HOURS, "validHours": sum(value is not None for value in local_values)},
        "monthlyCapture": months, "seasonalCapture": seasons,
        "quality": {"expectedHours": HOURS, "validHours": len(valid), "capturePercent": round(100 * len(valid) / HOURS, 3),
            "minimum": min(valid), "maximum": max(valid), "allMonthsPresent": all(month['validHours'] for month in months),
            "minimumMonthlyCapturePercent": min(month['capturePercent'] for month in months), "longestMissingRunHours": longest_gap,
            "eligibleForSeasonalComparison": True, "seasonalEligibilityRule": "At least 75% valid hourly observations annually and in every UTC meteorological season",
            "exclusionReason": None, "missingTreatment": "null; no interpolation, imputation or averaging of collocated monitors",
            "negativeReadingsExcluded": len(negatives), "negativeTreatment": "The app consistently excludes negative concentrations. All 18 original negative readings are retained in the source audit; EPA's own statistics may retain negatives and consequently differ.",
            "nonFiniteReadingsExcluded": 0, "nonHourlyReadingsExcluded": 0, "duplicateHours": 0, "conflictingDuplicateHours": 0,
            "outOfPeriodReadings": out_of_utc, "utcBoundaryMissingHours": 8,
            "boundaryNote": "The public 2024 file is indexed by local standard year. Its last eight local-year hours occur in UTC 2025; the first eight UTC-2024 hours would require the 2023 local archive and remain null. LocalYear retains all genuine 2024 local timestamps.",
            "qaStatus": qa_status, "certificationStatus": annual[0]['Certification Indicator'], "certificationEvidence": "annual_conc_by_monitor_2024.zip, parameter88101/POC3/sample-duration1HOUR; not an independent certification audit",
            "sourceQualityFlagsAvailable": True, "sourceQualifiers": dict(Counter(row['Qualifier'] or '(none)' for row in selected)),
            "eventTreatment": event_note, "regulatoryInterpretation": regulatory_note,
            "sourcePrecisionNote": "Original reported decimal concentrations retained; EPA truncation is applied only by the separate benchmark calculation.",
            "sampleDuration": "1 HOUR", "sampleDurationEvidence": "EPA hourly-file specification and matching annual 1 HOUR monitor summary",
            "spatialScope": "One monitoring location; not a citywide or population-weighted exposure estimate",
            "selectionReason": "Single POC 3, parameter88101, FEMmethod170; high hourly capture across all four seasons",
            "license": "Public domain US EPA AQS monitoring data", "licenseDocumentation": DOCS['reuse']},
        "sourceMetadata": {"parameterCode": "88101", "parameterName": "PM2.5 - Local Conditions", "poc": 3,
            "methodCode": "170", "methodType": "FEM", "methodName": selected[0]['Method Name'],
            "sampleDuration": "1 HOUR", "qualifierDefinitions": {"IH": {"meaning": "Fireworks", "type": "Informational Only"},
                "IT": {"meaning": "Wildfire-U. S.", "type": "Informational Only"}},
            "flaggedObservations": flagged, "excludedNegativeObservations": negatives,
            "annualHourlySummary": annual[0], "siteDescription": sites[0],
            "selectedMonitorDescription": next(row for row in monitors if row['POC'] == '3'),
            "primaryMonitorDescription": next(row for row in monitors if row['POC'] == '1'),
            "documentation": DOCS},
        "sources": [provenance[name] for name in FILES], "preparedAtUtc": datetime.now(timezone.utc).isoformat()}
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / "los-angeles-2024.json"
    output.write_text(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    raw_path = BASE / 'research' / 'EPA_LOS_ANGELES_2024_SELECTED.csv.gz'
    raw_text = io.StringIO(newline='')
    writer = csv.DictWriter(raw_text, fieldnames=list(selected[0]))
    writer.writeheader()
    writer.writerows(selected)
    raw_path.write_bytes(gzip.compress(raw_text.getvalue().encode('utf-8'), mtime=0))
    audit = {"selectedSite": "06-037-1103", "parameterCode": "88101", "poc": 3, "methodCode": "170", "rows": len(selected),
             "sourceFileHashes": provenance, "outputSha256": hashlib.sha256(output.read_bytes()).hexdigest(),
             "rawExtractSha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(), "quality": record['quality'],
             "monthlyCapture": months, "seasonalCapture": seasons, "localYearValidHours": record['localYear']['validHours'],
             "flaggedObservations": flagged, "excludedNegativeObservations": negatives,
             "annualHourlySummary": annual[0], "sourceFields": list(selected[0]), "documentation": DOCS}
    (BASE / 'research' / 'EPA_LOS_ANGELES_2024_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({"file": str(output), "quality": record['quality'], "monthlyCapture": months,
                      "seasonalCapture": seasons, "localYearValidHours": record['localYear']['validHours']}, ensure_ascii=False, indent=2), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--cache', type=Path, help='Reuse an explicit existing source-cache folder')
    args = parser.parse_args()
    global CACHE
    if args.cache:
        CACHE = args.cache
    with ThreadPoolExecutor(max_workers=4) as workers:
        provenance = dict(workers.map(fetch, FILES))
    print("Downloaded/cached:", {name: source['bytes'] for name, source in provenance.items()}, flush=True)
    with ThreadPoolExecutor(max_workers=4) as workers:
        datasets = dict(zip(FILES, workers.map(read_candidates, FILES)))
    audited = inventory(datasets)
    path = BASE / "research" / "EPA_CANDIDATES_2024.json"
    path.write_text(json.dumps({"sources": provenance, **audited}, indent=2, ensure_ascii=False), encoding='utf-8')
    print("Inventory written:", path, flush=True)
    print(json.dumps(audited['hourly'], indent=2))
    if not args.inventory:
        prepare(datasets, provenance)


if __name__ == '__main__':
    main()
