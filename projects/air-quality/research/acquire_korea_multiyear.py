"""Acquire adjacent complete Korea PM2.5 years without changing the 2024 files.

Run with Python's standard library. Raw responses and detailed audits stay outside
the website by default; only compact hourly records are deployed. Seoul uses the
same fixed 25 districts and >=20 valid-monitor hourly mean as the 2024 product.
Gyeonggi's public provincial query supplies Songbuk-dong station 131344.
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
import zipfile

from acquire_seoul_2024 import ENGLISH_NAMES, SOURCE_PAGE, DOWNLOAD_URL
from acquire_pyeongtaek_2024 import (PublicSession, PAGE, CATALOG,
    PROVINCIAL_CATALOG, LICENSE, LICENSE_BASIS, STATION_ID)

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
SEASONS = {"winter": (1, 2, 12), "spring": (3, 4, 5),
           "summer": (6, 7, 8), "autumn": (9, 10, 11)}
SEQUENCE = {2023: "34", 2025: "36"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    options = {"separators": (",", ":")} if compact else {"indent": 2}
    path.write_bytes((json.dumps(value, ensure_ascii=False, allow_nan=False, **options)
                      + "\n").encode("utf-8"))


def grid(year):
    start = datetime(year, 1, 1, tzinfo=KST)
    end = datetime(year + 1, 1, 1, tzinfo=KST)
    return start, int((end - start).total_seconds() / 3600)


def summarize(values, year):
    start, hours = grid(year)
    assert len(values) == hours
    months = [(start + timedelta(hours=i)).month for i in range(hours)]
    finite = [v for v in values if v is not None]
    monthly, seasonal = [], {}
    for month in range(1, 13):
        selected = [v for v, m in zip(values, months) if m == month]
        count = sum(v is not None for v in selected)
        monthly.append({"month": month, "expectedHours": len(selected),
                        "validHours": count, "capturePercent": round(100*count/len(selected), 3)})
    for name, included in SEASONS.items():
        selected = [v for v, m in zip(values, months) if m in included]
        count = sum(v is not None for v in selected)
        seasonal[name] = {"expectedHours": len(selected), "validHours": count,
                          "capturePercent": round(100*count/len(selected), 3)}
    gap = longest = zero_run = longest_zero = 0
    for value in values:
        gap = gap + 1 if value is None else 0
        zero_run = zero_run + 1 if value == 0 else 0
        longest, longest_zero = max(longest, gap), max(longest_zero, zero_run)
    return {"expectedHours": hours, "validHours": len(finite),
            "capturePercent": round(100*len(finite)/hours, 3),
            "minimum": min(finite) if finite else None, "maximum": max(finite) if finite else None,
            "mean": round(sum(finite)/len(finite), 6) if finite else None,
            "allMonthsPresent": all(m["validHours"] for m in monthly),
            "monthlyCapture": monthly, "seasonCapture": seasonal,
            "longestMissingRunHours": longest,
            "zeroValuesRetained": sum(v == 0 for v in finite),
            "longestZeroRunHours": longest_zero,
            "eligibleForSeasonalComparison": len(finite)/hours >= .75 and
                all(s["capturePercent"] >= 75 for s in seasonal.values())}


def number(token, counts):
    token = str(token).strip()
    if token in ("", "-", "-999", "-999.0", "None", "null"):
        counts["missing:" + token] += 1
        return None
    try:
        value = float(token)
    except ValueError:
        counts["nonnumeric"] += 1
        return None
    if not math.isfinite(value):
        counts["nonfinite"] += 1
        return None
    if value < 0:
        counts["negative"] += 1
        return None
    counts["zeros"] += value == 0
    return int(value) if value.is_integer() else value


def seoul_download(year, cache, refresh):
    path = cache / f"seoul-{year}.zip"
    meta_path = cache / f"seoul-{year}.download.json"
    fields = {"infId": "OA-2221", "seqNo": "", "seq": SEQUENCE[year], "infSeq": "3"}
    if refresh or not path.exists() or not meta_path.exists():
        request = urllib.request.Request(DOWNLOAD_URL,
            data=urllib.parse.urlencode(fields).encode("ascii"),
            headers={"User-Agent": "Mozilla/5.0 air-quality-comparison-research"})
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read(20_000_001)
            if len(raw) > 20_000_000 or not zipfile.is_zipfile(io.BytesIO(raw)):
                raise ValueError("Unexpected Seoul ZIP")
            path.write_bytes(raw)
            write(meta_path, {"url": DOWNLOAD_URL, "pageUrl": SOURCE_PAGE, "method": "POST",
                "postFields": fields, "bytes": len(raw), "sha256": digest(raw),
                "downloadedAtUtc": datetime.now(timezone.utc).isoformat(),
                "responseDate": response.headers.get("Date"),
                "contentType": response.headers.get("Content-Type")})
    raw = path.read_bytes()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta["postFields"] != fields or meta["sha256"] != digest(raw) or meta["bytes"] != len(raw):
        raise ValueError("Cached Seoul response differs from provenance")
    return raw, meta


def prepare_seoul(year, raw, metadata, destination, cache):
    start, hours = grid(year)
    archive = zipfile.ZipFile(io.BytesIO(raw))
    members = [entry for entry in archive.infolist() if not entry.is_dir()]
    if len(members) != 1:
        raise ValueError("Expected one Seoul CSV")
    csv_raw = archive.read(members[0])
    encoding = "utf-8-sig" if csv_raw.startswith(b"\xef\xbb\xbf") else "cp949"
    reader = csv.DictReader(io.StringIO(csv_raw.decode(encoding)))
    stations, seen, labels = {}, set(), set()
    token_counts = Counter()
    for row in reader:
        label, station_id, name = row["측정일시"], row["측정소코드"], row["측정소명"]
        instant = datetime.strptime(label, "%Y%m%d%H%M").replace(tzinfo=KST)
        offset = (instant - start).total_seconds()/3600
        if offset != int(offset) or not 0 <= offset < hours:
            raise ValueError(f"Out-of-grid Seoul label {label}")
        index, key = int(offset), (station_id, int(offset))
        if key in seen:
            raise ValueError(f"Duplicate Seoul station-hour {key}")
        seen.add(key)
        labels.add(label)
        if station_id not in stations:
            stations[station_id] = {"id": f"seoul-{station_id}", "name": ENGLISH_NAMES[name],
                "sourceName": name, "sourceStationId": station_id, "values": [None]*hours}
        elif stations[station_id]["sourceName"] != name:
            raise ValueError("Station name changed")
        stations[station_id]["values"][index] = number(row["초미세먼지(㎍/㎥)"], token_counts)
    expected_ids = set(json.loads((destination / "seoul-2024.json").read_text(encoding="utf-8"))["station"]["stationIds"])
    if set(stations) != expected_ids or len(labels) != hours:
        raise ValueError("Seoul district identities or complete source hours differ from 2024")
    ordered = sorted(stations.values(), key=lambda s: s["name"])
    audits = {}
    for station in ordered:
        summary = summarize(station["values"], year)
        audits[station["sourceStationId"]] = summary
        station.update({k: summary[k] for k in ("validHours", "capturePercent")})
        station["eligibleForSeasonalComparison"] = summary["eligibleForSeasonalComparison"]
        station["seasonCapture"] = summary["seasonCapture"]
    counts = [sum(s["values"][i] is not None for s in ordered) for i in range(hours)]
    network = [round(sum(s["values"][i] for s in ordered if s["values"][i] is not None)/n, 2)
               if n >= 20 else None for i, n in enumerate(counts)]
    local_summary, utc_summary = summarize(network, year), summarize(network[9:]+[None]*9, year)
    if not local_summary["eligibleForSeasonalComparison"]:
        raise ValueError("Seoul network failed annual/seasonal 75% rule")
    modified = "2025-11-07" if year == 2023 else "2026-04-01"
    source = {**metadata, "provider": "Seoul Metropolitan Government", "datasetId": "OA-2221",
        "title": f"Seoul hourly air-quality archive, {year}", "fileModifiedDate": modified,
        "archiveName": f"서울시_기간별_시간평균_대기환경_정보_{year}.zip",
        "csvSha256": digest(csv_raw), "csvBytes": len(csv_raw), "encoding": encoding,
        "license": "KOGL Type 1 (attribution; commercial reuse and adaptation allowed)",
        "licenseUrl": "https://www.kogl.or.kr/info/licenseType1.do",
        "attribution": f"Source: Seoul Metropolitan Government, Seoul Open Data Plaza OA-2221; {year} hourly air-quality archive, modified {modified}. Extracted and aggregated for this comparison.",
        "qaStatus": "Archived municipal observations; final national ratification status is not supplied.",
        "qualityFlagsAvailable": False}
    convention = {"source_timezone": "Asia/Seoul", "source_utc_offset_minutes": 540,
        "source_label_field": "측정일시", "source_label_format": "YYYYMMDDHHmm",
        "source_first_label": min(labels), "source_last_label": max(labels),
        "hour_interval_semantics": "The portal describes hourly means but does not explicitly identify hour-start versus hour-end. Source labels are preserved without a one-hour shift.",
        "utc_conversion": "Subtract nine hours from the source local label; no daylight-saving time.",
        "interpretation_limit": "Exact simultaneous-hour comparisons may have a one-hour convention offset until confirmed with the provider."}
    definition = "Unweighted mean of valid hourly concentrations at the same 25 district monitors used in 2024; at least 20 monitors required per hour. Fixed monitor membership preserves the geographic definition across years. District-specific annual and seasonal completeness is audited separately. Not a population-weighted exposure estimate."
    local_start = start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    standardized = {"schemaVersion": 1, "id": "seoul", "city": "Seoul", "year": year,
        "pollutant": "PM2.5", "units": "µg/m³", "timeZone": "Asia/Seoul", "standardOffsetMinutes": 540,
        "station": {"id": "seoul-network-mean", "name": "Mean of Seoul's 25 district monitors",
            "provider": "Seoul Metropolitan Government", "type": "Mean of 25 district monitors",
            "url": SOURCE_PAGE, "aggregation": definition, "minimumStationsPerHour": 20,
            "stationCount": 25, "stationIds": [s["sourceStationId"] for s in ordered]},
        "startUtc": f"{year}-01-01T00:00:00Z", "intervalMinutes": 60,
        "periodBasis": "UTC calendar year; original local-year observations also retained in localYear",
        "timeConvention": convention, "values": network[9:]+[None]*9, "stationCounts": counts[9:]+[0]*9,
        "monthlyCapture": utc_summary["monthlyCapture"],
        "quality": {**{k: v for k, v in utc_summary.items() if k != "monthlyCapture"},
            "missingTreatment": "null; retain numeric zero; no imputation or interpolation; network requires at least 20 of 25 monitors",
            "negativeReadingsExcluded": token_counts["negative"], "nonFiniteReadingsExcluded": token_counts["nonfinite"],
            "nonnumericReadingsExcluded": token_counts["nonnumeric"], "sourceRows": len(seen),
            "sourceAbsentStationHours": hours*25-len(seen), "utcBoundaryMissingHours": 9,
            "outOfPeriodReadings": 9, "duplicateHours": 0, "conflictingDuplicateHours": 0,
            "nonHourlyReadingsExcluded": 0, "qaStatus": source["qaStatus"], "qualityFlagsAvailable": False},
        "sources": [source],
        "localYear": {"year": year, "startUtc": local_start, "intervalMinutes": 60, "values": network,
            "stationCounts": counts, "validHours": local_summary["validHours"], "capturePercent": local_summary["capturePercent"]},
        "preparedAtUtc": datetime.now(timezone.utc).isoformat()}
    supplement = {"schemaVersion": 1, "city": "Seoul", "year": year, "pollutant": "PM2.5",
        "units": "µg/m³", "timeZone": "Asia/Seoul", "startUtc": local_start, "intervalMinutes": 60,
        "sources": [source], "timeConvention": convention,
        "network": {"id": "seoul-network-mean", "name": "Mean of Seoul's 25 district monitors",
            "values": network, "stationCounts": counts, "stationIds": [s["id"] for s in ordered],
            "minimumStationsPerHour": 20, "definition": definition,
            "validHours": local_summary["validHours"], "capturePercent": local_summary["capturePercent"]},
        "stations": ordered, "sourceSha256": digest(raw)}
    write(destination / f"seoul-{year}.json", standardized, True)
    write(destination / f"seoul-stations-{year}.json", supplement, True)
    audit = {"year": year, "sourceRows": len(seen), "sourceUniqueHourLabels": len(labels),
             "districts": audits, "tokenCounts": dict(token_counts), "networkLocal": local_summary,
             "networkUtc": utc_summary, "monitorCountDistribution": dict(sorted(Counter(counts).items())),
             "sources": [source]}
    write(cache / f"seoul-{year}.quality.json", audit)
    return {"city": "Seoul", "year": year, "local": local_summary, "utc": utc_summary,
            "sourceRows": len(seen), "districtCaptureRange": [min(s["capturePercent"] for s in ordered), max(s["capturePercent"] for s in ordered)]}


def acquire_pyeongtaek(year, cache, refresh):
    responses, session = [], None
    for month in range(1, 13):
        path = cache / f"gyeonggi-songbuk-{year}-{month:02d}.json"
        meta_path = path.with_suffix(".download.json")
        fields = {"op": "getByLoc", "fromDt": f"{year}-{month:02d}-01",
            "toDt": f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}",
            "locCd": STATION_ID, "typeCd": "1"}
        if refresh or not path.exists() or not meta_path.exists():
            for attempt in range(3):
                try:
                    session = session or PublicSession()
                    raw, metadata = session.query(fields)
                    break
                except (OSError, TimeoutError) as error:
                    if attempt == 2:
                        raise
                    print(f"Retry {path.name} after {type(error).__name__}", flush=True)
                    session = None
                    time.sleep(2)
            path.write_bytes(raw)
            write(meta_path, metadata)
            print(f"Downloaded {path.name}: {len(raw):,}bytes", flush=True)
        raw = path.read_bytes()
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if metadata["bytes"] != len(raw) or metadata["sha256"] != digest(raw) or metadata["postFields"] != fields:
            raise ValueError("Cached Gyeonggi response differs from provenance")
        responses.append((raw, metadata))
    return responses


def prepare_pyeongtaek(year, responses, destination, cache):
    start, hours = grid(year)
    values, seen, labels = [None]*hours, set(), []
    tokens = Counter()
    summary_rows = 0
    for month, (raw, _) in enumerate(responses, 1):
        initial = len(seen)
        summaries = 0
        for row in json.loads(raw)["list"]:
            if row.get("odr") != 1:
                if row.get("odr") not in (2, 3, 4):
                    raise ValueError("Unexpected provincial non-observation row")
                summaries += 1
                continue
            label = row["dataDt"]
            instant = datetime.strptime(label, "%Y%m%d%H").replace(tzinfo=KST)
            offset = (instant-start).total_seconds()/3600
            if instant.month != month or offset != int(offset) or not 0 <= offset < hours or int(offset) in seen:
                raise ValueError(f"Duplicate/out-of-grid Gyeonggi label {label}")
            seen.add(int(offset))
            labels.append(label)
            values[int(offset)] = number(row.get("pm25", ""), tokens)
        if len(seen)-initial != calendar.monthrange(year, month)[1]*24 or summaries != 3:
            raise ValueError(f"Incomplete provincial source labels or summary rows in {year}-{month:02d}")
        summary_rows += summaries
    local, utc = summarize(values, year), summarize(values[9:]+[None]*9, year)
    if not local["eligibleForSeasonalComparison"] or not utc["eligibleForSeasonalComparison"]:
        raise ValueError("Pyeongtaek source failed annual/seasonal 75% rule: "+json.dumps(local))
    sources = [{**meta, "provider": "Gyeonggi Institute of Health and Environment",
        "attribution": f"Source: Gyeonggi Institute of Health and Environment, Gyeonggi Air Quality Information Service; raw hourly PM2.5, Songbuk-dong (송북동), Pyeongtaek, station 131344, {year}.",
        "license": LICENSE, "licenseEvidence": CATALOG, "catalogUrl": PROVINCIAL_CATALOG,
        "licenseBasis": LICENSE_BASIS} for _, meta in responses]
    convention = {"source_timezone": "Asia/Seoul", "source_utc_offset_minutes": 540,
        "source_label_field": "dataDt", "source_label_format": "YYYYMMDDHH (00–23)",
        "source_first_label": min(labels), "source_last_label": max(labels),
        "hour_interval_semantics": "Original provincial JSON dataDt labels 00–23 preserved without a one-hour shift; public page adds one for display as 01–24.",
        "utc_conversion": "Subtract nine hours from each original local dataDt label; no daylight-saving time.",
        "interpretation_limit": "Physical interval-start/end dictionary not located; original source-day labels preserved.",
        "evidence": PAGE, "utc_boundary": "First nine local-year hours precede the UTC year; final nine UTC-year hours unavailable in this local-year source and remain null."}
    quality = {**{k: v for k, v in utc.items() if k != "monthlyCapture"},
        "qaStatus": "Provincial raw hourly observations, before final confirmation. Reported numeric zeros retained; no per-reading QA flags or detection-limit metadata supplied.",
        "qualityFlagsAvailable": False, "ratificationStatus": "Raw provincial measurements; no NIER final-ratification claim.",
        "missingTreatment": "Missing tokens and nonfinite/nonnumeric/negative readings are null; numeric zero retained; no interpolation or imputation.",
        "negativeReadingsExcluded": tokens["negative"], "nonFiniteReadingsExcluded": tokens["nonfinite"],
        "nonnumericReadingsExcluded": tokens["nonnumeric"], "sourceRows": len(seen),
        "sourceSummaryRowsExcluded": summary_rows, "sourceMissingTokens": {k[8:]: v for k,v in tokens.items() if k.startswith("missing:")},
        "outOfPeriodReadings": 9, "utcBoundaryMissingHours": 9, "duplicateHours": 0,
        "conflictingDuplicateHours": 0, "nonHourlyReadingsExcluded": 0,
        "license": LICENSE, "licenseEvidence": CATALOG, "licenseBasis": LICENSE_BASIS,
        "spatialScope": "One urban-air monitor, Songbuk-dong, Pyeongtaek; not a citywide average.",
        "selectionReason": "Same station 131344 as 2024; annual and every-season capture at least 75%, no concentration-based selection."}
    record = {"schemaVersion": 1, "id": "pyeongtaek", "city": "Pyeongtaek", "year": year,
        "label": "Pyeongtaek · Songbuk-dong", "pollutant": "PM2.5", "units": "µg/m³",
        "timeZone": "Asia/Seoul", "standardOffsetMinutes": 540,
        "station": {"id": STATION_ID, "name": "Songbuk-dong", "sourceName": "송북동",
            "provider": "Gyeonggi Institute of Health and Environment", "type": "Urban-air monitoring station (도시대기)", "url": PAGE},
        "startUtc": f"{year}-01-01T00:00:00Z", "intervalMinutes": 60,
        "periodBasis": "UTC calendar year; original local-year observations retained in localYear",
        "timeConvention": convention, "values": values[9:]+[None]*9,
        "monthlyCapture": utc["monthlyCapture"], "quality": quality, "sources": sources,
        "localYear": {"year": year, "startUtc": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "intervalMinutes": 60, "values": values, "validHours": local["validHours"], "capturePercent": local["capturePercent"]},
        "preparedAtUtc": datetime.now(timezone.utc).isoformat()}
    write(destination / f"pyeongtaek-{year}.json", record, True)
    write(cache / f"pyeongtaek-{year}.quality.json", {"year": year, "local": local, "utc": utc,
        "tokenCounts": dict(tokens), "sourceUniqueHourLabels": len(seen), "sources": sources})
    return {"city": "Pyeongtaek", "year": year, "local": local, "utc": utc}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, nargs="+", default=[2023, 2025])
    parser.add_argument("--cities", nargs="+", choices=["seoul", "pyeongtaek"], default=["seoul", "pyeongtaek"])
    parser.add_argument("--cache", type=Path, default=ROOT.parents[2]/"air-quality-comparison"/"research"/"extended")
    parser.add_argument("--destination", type=Path, default=ROOT/"data")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    results = []
    for year in args.years:
        if "seoul" in args.cities:
            raw, meta = seoul_download(year, args.cache, args.refresh)
            results.append(prepare_seoul(year, raw, meta, args.destination, args.cache))
        if "pyeongtaek" in args.cities:
            results.append(prepare_pyeongtaek(year, acquire_pyeongtaek(year, args.cache, args.refresh), args.destination, args.cache))
        print(json.dumps(results[-1], ensure_ascii=True), flush=True)
    write(args.cache / "korea-extended-summary.json", results)
    packaged_audits = []
    for year in SEQUENCE:
        for city in ("seoul", "pyeongtaek"):
            record_path = args.destination / f"{city}-{year}.json"
            audit_path = args.cache / f"{city}-{year}.quality.json"
            if record_path.exists() and audit_path.exists():
                audit = json.loads(audit_path.read_text(encoding="utf-8"))
                for output_path in ([record_path, args.destination / f"seoul-stations-{year}.json"]
                                    if city == "seoul" else [record_path]):
                    if not output_path.exists():
                        raise ValueError("Prepared district supplement missing")
                    raw_output = output_path.read_bytes()
                    audit.setdefault("outputs", []).append({"file": output_path.name,
                        "bytes": len(raw_output), "sha256": digest(raw_output)})
                packaged_audits.append({"city": city, **audit})
    write(ROOT / "research" / "korea-multiyear-audit.json", {
        "schemaVersion": 1, "preparedAtUtc": datetime.now(timezone.utc).isoformat(),
        "method": "Fixed source identities, source hourly labels retained, finite nonnegative PM2.5 only, numeric zeros retained, no imputation; Seoul fixed 25 monitor membership with at least 20 valid per hour.",
        "records": packaged_audits})
    print(json.dumps([{ "city": r["city"], "year": r["year"],
        "localValidHours": r["local"]["validHours"],
        "localCapturePercent": r["local"]["capturePercent"],
        "utcValidHours": r["utc"]["validHours"]} for r in results], indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
