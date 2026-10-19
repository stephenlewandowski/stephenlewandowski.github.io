"""Acquire observed hourly 2024 PM2.5 from public OpenAQ and LondonAir sources.

Python standard library only; LondonAir annual RData decoding also uses Rscript.
Raw responses are cached in the system temporary
directory; the published JSON includes every response's SHA256 for provenance.
Missing, non-finite and negative readings become null, never zero or interpolated.
The regular grid covers UTC 2024 (8784 hours), with local zones kept as metadata.
"""
from __future__ import annotations

import calendar
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "data" / "comparisons"
CACHE = Path(tempfile.gettempdir()) / "air-quality-2024-public-source"
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2025, 1, 1, tzinfo=timezone.utc)
HOURS = 8784


def fetch(url: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".bin")
    if path.exists():
        raw = path.read_bytes()
        downloaded = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    else:
        for attempt in range(4):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "ResearchAirQualityComparison/1.0"})
                with urllib.request.urlopen(request, timeout=90) as response:
                    raw = response.read()
                path.write_bytes(raw)
                downloaded = datetime.now(timezone.utc).isoformat()
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
    return raw, {"url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                 "bytes": len(raw), "downloadedAtUtc": downloaded}


def monthly(values):
    output = []
    offset = 0
    for month in range(1, 13):
        expected = calendar.monthrange(2024, month)[1] * 24
        valid = sum(v is not None for v in values[offset:offset + expected])
        output.append({"month": month, "expectedHours": expected, "validHours": valid,
                       "capturePercent": round(100 * valid / expected, 2)})
        offset += expected
    return output


def make_output(city, slug, zone, station, records, sources, extra, minute_offset=0):
    grid_start = START + timedelta(minutes=minute_offset)
    values = [None] * HOURS
    counts = {"negativeReadingsExcluded": 0, "nonFiniteReadingsExcluded": 0,
              "outOfPeriodReadings": 0, "duplicateHours": 0, "conflictingDuplicateHours": 0,
              "nonHourlyReadingsExcluded": 0}
    for stamp, raw_value in sorted(records, key=lambda item: item[0]):
        elapsed = (stamp.astimezone(timezone.utc) - grid_start).total_seconds()
        if elapsed < 0 or elapsed >= HOURS * 3600:
            counts["outOfPeriodReadings"] += 1
            continue
        if elapsed % 3600:
            counts["nonHourlyReadingsExcluded"] += 1
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            counts["nonFiniteReadingsExcluded"] += 1
            continue
        if not math.isfinite(value):
            counts["nonFiniteReadingsExcluded"] += 1
            continue
        if value < 0:
            counts["negativeReadingsExcluded"] += 1
            continue
        index = int(elapsed // 3600)
        if values[index] is not None:
            counts["duplicateHours"] += 1
            if values[index] != value:
                counts["conflictingDuplicateHours"] += 1
                raise ValueError(f"Conflicting duplicate for {city} {stamp}")
        values[index] = round(value, 3)
    valid_values = [v for v in values if v is not None]
    month_counts = monthly(values)
    gap = longest_gap = 0
    for value in values:
        gap = gap + 1 if value is None else 0
        longest_gap = max(longest_gap, gap)
    eligible = all(m["capturePercent"] >= 75 for m in month_counts)
    result = {
        "schemaVersion": 1, "id": slug, "city": city, "year": 2024,
        "pollutant": "PM2.5", "units": "µg/m³", "timeZone": zone,
        "station": station, "startUtc": grid_start.isoformat().replace("+00:00", "Z"), "intervalMinutes": 60,
        "periodBasis": "UTC calendar year; local times are available using the stated time zone",
        "values": values, "monthlyCapture": month_counts,
        "quality": {"expectedHours": HOURS, "validHours": len(valid_values),
                    "capturePercent": round(100 * len(valid_values) / HOURS, 2),
                    "minimum": min(valid_values) if valid_values else None,
                    "maximum": max(valid_values) if valid_values else None,
                    "allMonthsPresent": all(m["validHours"] > 0 for m in month_counts),
                    "minimumMonthlyCapturePercent": min(m["capturePercent"] for m in month_counts),
                    "longestMissingRunHours": longest_gap,
                    "eligibleForSeasonalComparison": eligible,
                    "seasonalEligibilityRule": "At least 75% valid hourly readings in every UTC calendar month",
                    "exclusionReason": None if eligible else "One or more months have less than 75% valid hourly readings",
                    "missingTreatment": "null; no interpolation or imputation",
                    **counts, **extra},
        "sources": sorted(sources, key=lambda item: item["url"]),
        "preparedAtUtc": datetime.now(timezone.utc).isoformat(),
    }
    assert len(values) == HOURS
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{slug}-2024.json"
    path.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"file": str(path), "city": city, "quality": result["quality"],
                      "monthlyCapture": month_counts}), flush=True)
    return result


def archive_keys(location, year):
    url = "https://openaq-data-archive.s3.amazonaws.com/?" + urllib.parse.urlencode({
        "list-type": "2", "prefix": f"records/csv.gz/locationid={location}/year={year}/", "max-keys": 1000})
    raw, source = fetch(url)
    tree = ET.fromstring(raw)
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    if tree.findtext("s:IsTruncated", namespaces=ns) != "false":
        raise ValueError("Archive listing truncated")
    return [n.text for n in tree.findall("s:Contents/s:Key", ns)], source


def openaq(location, city, slug, zone):
    keys, listing_source = archive_keys(location, 2024)
    # Adjacent objects can contain hours at the year boundary. Only fetch the
    # immediately adjacent day object, if present; make_output retains UTC 2024.
    for year, suffix in ((2023, "20231231.csv.gz"), (2025, "20250101.csv.gz")):
        adjacent, _ = archive_keys(location, year)
        keys.extend(k for k in adjacent if k.endswith(suffix))
    records, sources = [], [listing_source]
    sensor_ids, units = set(), set()
    station = {"id": str(location), "name": f"{city} (OpenAQ {location})", "provider": "AirNow via OpenAQ",
               "type": "Single monitoring location", "url": f"https://explore.openaq.org/locations/{location}"}

    def get_day(key):
        raw, source = fetch("https://openaq-data-archive.s3.amazonaws.com/" + urllib.parse.quote(key, safe="/="))
        text = gzip.decompress(raw).decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text))), source

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(get_day, k) for k in keys]
        for index, future in enumerate(as_completed(futures), 1):
            rows, source = future.result()
            sources.append(source)
            for row in rows:
                if row.get("parameter") != "pm25":
                    continue
                sensor_ids.add(row.get("sensors_id"))
                units.add(row.get("units"))
                records.append((datetime.fromisoformat(row["datetime"]), row.get("value")))
                station["latitude"], station["longitude"] = float(row["lat"]), float(row["lon"])
            if index % 75 == 0:
                print(f"{city}: downloaded {index}/{len(keys)} daily archive files", flush=True)
    if len(sensor_ids) != 1:
        raise ValueError(f"Expected one PM2.5 sensor, found {sensor_ids}")
    station["sensorId"] = next(iter(sensor_ids))
    return make_output(city, slug, zone, station, records, sources,
                       {"archiveObjects": len(keys), "sourceUnitStrings": sorted(units),
                        "unitNote": "OpenAQ PM2.5 mass concentration in micrograms per cubic metre",
                        "sourceTimestamps": ("Offset-aware archive measurement timestamps retained without rounding; Delhi reports at UTC xx:30"
                                             if slug == "delhi" else "Offset-aware archive measurement timestamps retained at their reported UTC hour without rounding"),
                        "license": "US Public Domain as shown on the OpenAQ location page",
                        "sourceQualityFlagsAvailable": False,
                        "ratificationStatus": "Not supplied in the archived AirNow/OpenAQ rows",
                        "spatialScope": "One monitor; not a citywide or population-weighted estimate"},
                       minute_offset=30 if slug == "delhi" else 0)


def london_api():
    urls = []
    for month in range(1, 13):
        start = f"2024-{month:02d}-01"
        end = f"2024-{month+1:02d}-01" if month < 12 else "2025-01-01"
        urls.append("https://api.erg.ic.ac.uk/AirQuality/Data/SiteSpecies/SiteCode=BQ7/SpeciesCode=PM25/"
                    f"StartDate={start}/EndDate={end}/Json")
    records, sources = [], []

    def get_month(url):
        raw, source = fetch(url)
        body = json.loads(raw)
        data = body["RawAQData"].get("Data", [])
        if isinstance(data, dict):
            data = [data]
        return data, source

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(get_month, url) for url in urls]
        for future in as_completed(futures):
            rows, source = future.result()
            sources.append(source)
            for row in rows:
                stamp = datetime.fromisoformat(row["@MeasurementDateGMT"].replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                records.append((stamp, row.get("@Value")))
    station = {"id": "BQ7", "name": "Bexley – Belvedere West", "provider": "London Air Quality Network / Imperial College London",
               "type": "Urban Background; single monitoring location", "url": "https://www.londonair.org.uk/london/asp/publicdetails.asp?site=BQ7"}
    return make_output("London", "london", "Europe/London", station, records, sources,
                       {"sourceTimestamps": "LondonAir MeasurementDateGMT is GMT throughout the year",
                        "license": "Open Government Licence v2; London Air Quality Network / Imperial College London",
                        "spatialScope": "One urban-background monitor; not a citywide or population-weighted estimate"})


def rscript_path():
    path = os.environ.get("AQ_RSCRIPT") or shutil.which("Rscript")
    if not path:
        raise RuntimeError("Rscript is needed to decode the public LondonAir annual RData archive")
    return path


def london():
    """Read the public annual file used by openair::importImperial()."""
    url = "https://londonair.org.uk/r_data/HP1_2024.RData"
    raw, source = fetch(url)
    path = CACHE / "HP1_2024.RData"
    path.write_bytes(raw)
    csv_path = CACHE / "HP1_2024.csv"
    code = (f'load("{path.as_posix()}"); '
            'stopifnot("pm25" %in% names(x)); '
            'd <- data.frame(timestamp=format(x$date,tz="GMT",format="%Y-%m-%dT%H:%M:%SZ"),value=x$pm25); '
            f'write.csv(d,file="{csv_path.as_posix()}",row.names=FALSE,na=""); '
            'cat(paste(names(x),collapse=","))')
    converted = subprocess.run([rscript_path(), "--vanilla", "-e", code], check=True, capture_output=True)
    source_fields = converted.stdout.decode("utf-8").strip().split(",")
    records = [(datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")), row["value"])
               for row in csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8")))]
    _, metadata_source = fetch("https://londonair.org.uk/r_data/sites.RData")
    station = {"id": "HP1", "name": "Lewisham – Honor Oak Park", "provider": "London Air Quality Network / Imperial College London",
               "type": "Urban Background; single monitoring location", "latitude": 51.44967, "longitude": -0.03741536,
               "url": "https://www.londonair.org.uk/london/asp/publicdetails.asp?site=HP1"}
    return make_output("London", "london", "Europe/London", station, records, [source, metadata_source],
                       {"sourceTimestamps": "RData POSIXct instants converted to GMT, as required by openair::importImperial(); no summer-time shift",
                        "sourcePrecisionNote": "PM2.5 values serialized to three decimal places; original annual response retained by hash",
                        "license": "Open Government Licence v2; London Air Quality Network / Imperial College London",
                        "licenseEvidence": "LondonAir network API documentation specifies OGL v2; the annual RData object does not embed a separate license statement",
                        "licenseDocumentation": "https://api.erg.ic.ac.uk/AirQuality/Information/Documentation/pdf",
                        "ratificationStatus": "Not provided in the annual RData archive; no ratification claim is made",
                        "sourceQualityFlagsAvailable": False,
                        "sourceFields": source_fields,
                        "selectionReason": "Urban-background monitor with at least 75% valid data in every month; HP1 has 99.90% annual capture",
                        "sourceDocumentation": "https://github.com/openair-project/openair/blob/main/R/importImperial.R",
                        "spatialScope": "One urban-background monitor; not a citywide or population-weighted estimate"})


def london_candidates():
    """Inspect candidate coverage using the network's documented annual archive."""
    for site in ("BQ7", "BL0", "LH0", "HP1", "CW3", "WM0", "KC1"):
        try:
            url = f"https://londonair.org.uk/r_data/{site}_2024.RData"
            raw, source = fetch(url)
            path = CACHE / f"{site}_2024.RData"
            path.write_bytes(raw)
            code = (f'load("{path.as_posix()}"); '
                    'if ("pm25" %in% names(x)) { '
                    'print(sum(!is.na(x$pm25) & x$pm25 >= 0)); '
                    'print(tapply(!is.na(x$pm25) & x$pm25 >= 0,format(x$date,"%m",tz="GMT"),sum)) '
                    '} else print(names(x))')
            result = subprocess.run([rscript_path(), "--vanilla", "-e", code], capture_output=True, text=True, check=True)
            print(site, source["sha256"], result.stdout, flush=True)
        except Exception as error:
            print(site, str(error), flush=True)


if __name__ == "__main__":
    jobs = {"delhi": lambda: openaq(8118, "Delhi", "delhi", "Asia/Kolkata"),
            "beijing": lambda: openaq(8833, "Beijing", "beijing", "Asia/Shanghai"),
            "london": london, "london_candidates": london_candidates}
    selected = sys.argv[1:] or ["delhi", "beijing", "london"]
    for name in selected:
        if name not in jobs:
            raise SystemExit(f"Unknown city: {name}")
        jobs[name]()
