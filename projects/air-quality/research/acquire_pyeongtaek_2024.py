"""Acquire Gyeonggi Province's independently published hourly PM2.5 data.

Standard library only. Public session/CSRF values are obtained at runtime and
never saved. The source is the provincial monitoring site's documented station
query, corresponding to the province's unrestricted 1-hour concentration
product catalogued as DATA.GO.KR 15122939 / Gyeonggi E20A4WR0UKVQFVTXNT7D33593740.
This is the province's raw product; national final ratification is not claimed.
"""

from __future__ import annotations

import argparse
import calendar
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import http.cookiejar
import json
import math
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "pyeongtaek"
CACHE = FOLDER / ".cache"
PAGE = "https://air.gg.go.kr/default/esData.do?mCode=A010010000"
QUERY = "https://air.gg.go.kr/default/tms.do"
CATALOG = "https://www.data.go.kr/data/15122939/fileData.do"
PROVINCIAL_CATALOG = "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=E20A4WR0UKVQFVTXNT7D33593740&infSeq=1"
STATION_ID = "131344"
KST = timezone(timedelta(hours=9))
START = datetime(2024, 1, 1, tzinfo=KST)
HOURS = 8784
SEASONS = {"Winter (Jan–Feb, Dec)": (1, 2, 12), "Spring (Mar–May)": (3, 4, 5),
           "Summer (Jun–Aug)": (6, 7, 8), "Autumn (Sep–Nov)": (9, 10, 11)}
LICENSE = "Unrestricted reuse (이용허락범위 제한 없음), specified for Gyeonggi's 1-hour concentration product in official DATA.GO.KR catalog 15122939."
ATTRIBUTION = "Source: Gyeonggi Institute of Health and Environment, Gyeonggi Air Quality Information Service; raw hourly PM2.5 observations, Songbuk-dong (송북동), Pyeongtaek, station 131344, 2024."
LICENSE_BASIS = "The official catalog identifies Gyeonggi Institute of Health and Environment as producer of the province's raw 1-hour station-concentration product and explicitly permits unrestricted reuse. These responses are independently acquired from that institute's public station-query interface for the same hourly concentration product. This is a product-level catalog attribution, not a blanket license inferred from the website footer."


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    options = {"ensure_ascii": False, "allow_nan": False}
    options.update({"separators": (",", ":")} if compact else {"indent": 2})
    path.write_text(json.dumps(value, **options) + "\n", encoding="utf-8")


class PublicSession:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with self.opener.open(PAGE, timeout=45) as response:
            text = response.read().decode("utf-8")
        match = re.search(r'name="_csrf" value="([^"]+)"', text)
        if not match:
            raise ValueError("Public query page did not supply its session CSRF value")
        self.csrf = match.group(1)
        # The provincial display adds one to the raw 00–23 dataDt hour. Retain
        # that raw label without importing the national export's interpretation.
        if "return parseInt(dt)+1" not in text or "list[i].dataDt" not in text:
            raise ValueError("Provincial display convention changed; review timestamp mapping")

    def query(self, fields):
        request = urllib.request.Request(QUERY, data=urllib.parse.urlencode(fields).encode("ascii"),
            headers={"X-CSRF-TOKEN": self.csrf, "Referer": PAGE,
                     "User-Agent": "Mozilla/5.0 air-quality-comparison-research"})
        with self.opener.open(request, timeout=75) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Unexpectedly large station query")
            metadata = {"url": QUERY, "pageUrl": PAGE, "method": "POST", "postFields": fields,
                        "bytes": len(raw), "sha256": sha256(raw),
                        "downloadedAtUtc": datetime.now(timezone.utc).isoformat(),
                        "responseDate": response.headers.get("Date"),
                        "contentType": response.headers.get("Content-Type")}
        json.loads(raw)
        return raw, metadata


def acquire(refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    session = None
    responses = []
    for month in range(1, 13):
        path = CACHE / f"gyeonggi-songbuk-2024-{month:02d}.json"
        metadata_path = path.with_suffix(".download.json")
        fields = {"op": "getByLoc", "fromDt": f"2024-{month:02d}-01",
                  "toDt": f"2024-{month:02d}-{calendar.monthrange(2024, month)[1]:02d}",
                  "locCd": STATION_ID, "typeCd": "1"}
        if refresh or not path.exists() or not metadata_path.exists():
            session = session or PublicSession()
            raw, metadata = session.query(fields)
            path.write_bytes(raw)
            write_json(metadata_path, metadata)
            print(f"Downloaded {path.name}: {len(raw):,} bytes", flush=True)
        raw = path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["bytes"] != len(raw) or metadata["sha256"] != sha256(raw) or metadata["postFields"] != fields:
            raise ValueError(f"Cached public response differs from its source metadata: {path}")
        responses.append((raw, metadata))
    return responses


def summarize(values):
    assert len(values) == HOURS
    months = [(datetime(2024, 1, 1) + timedelta(hours=index)).month for index in range(HOURS)]
    valid = [value for value in values if value is not None]
    monthly = []
    for month in range(1, 13):
        selected = [value for value, number in zip(values, months) if number == month]
        count = sum(value is not None for value in selected)
        monthly.append({"month": month, "expectedHours": len(selected), "validHours": count,
                        "capturePercent": round(count / len(selected) * 100, 3)})
    seasons = {}
    for name, included in SEASONS.items():
        selected = [value for value, month in zip(values, months) if month in included]
        count = sum(value is not None for value in selected)
        seasons[name] = {"expectedHours": len(selected), "validHours": count,
                         "capturePercent": round(count / len(selected) * 100, 3)}
    gap = longest_gap = zero_run = longest_zero = 0
    for value in values:
        gap = gap + 1 if value is None else 0
        zero_run = zero_run + 1 if value == 0 else 0
        longest_gap = max(gap, longest_gap)
        longest_zero = max(zero_run, longest_zero)
    return {"expectedHours": HOURS, "validHours": len(valid),
            "capturePercent": round(len(valid) / HOURS * 100, 3),
            "minimum": min(valid) if valid else None, "maximum": max(valid) if valid else None,
            "mean": round(sum(valid) / len(valid), 6) if valid else None,
            "allMonthsPresent": all(item["validHours"] > 0 for item in monthly),
            "longestMissingRunHours": longest_gap, "zeroValuesRetained": sum(value == 0 for value in valid),
            "longestZeroRunHours": longest_zero, "monthlyCapture": monthly, "seasonCapture": seasons,
            "eligibleForSeasonalComparison": len(valid) / HOURS >= .75
                and all(item["capturePercent"] >= 75 for item in seasons.values())}


def prepare(responses):
    local_values = [None] * HOURS
    seen = set()
    labels = []
    missing_tokens = Counter()
    audit_months = []
    negative = nonfinite = nonnumeric = summary_rows = 0
    for month, (raw, metadata) in enumerate(responses, 1):
        data = json.loads(raw)
        first_count = len(seen)
        summaries = 0
        month_labels = []
        for row in data["list"]:
            if row.get("odr") != 1:
                if row.get("odr") not in (2, 3, 4):
                    raise ValueError("Unexpected provincial non-observation row")
                summaries += 1
                continue
            label = row["dataDt"]
            if not re.fullmatch(r"2024\d{6}", label):
                raise ValueError(f"Unexpected provincial hourly label: {label}")
            instant = datetime.strptime(label, "%Y%m%d%H").replace(tzinfo=KST)
            if instant.month != month:
                raise ValueError("Provincial query returned data outside its requested month")
            index = int((instant - START).total_seconds() // 3600)
            if not 0 <= index < HOURS or index in seen:
                raise ValueError(f"Duplicate/out-of-year provincial source hour: {label}")
            seen.add(index)
            labels.append(label)
            month_labels.append(label)
            token = str(row.get("pm25", "")).strip()
            if token in ("", "-", "-999", "-999.0", "None", "null"):
                missing_tokens[token] += 1
                continue
            try:
                value = float(token)
            except ValueError:
                nonnumeric += 1
                missing_tokens[token] += 1
                continue
            if not math.isfinite(value):
                nonfinite += 1
            elif value < 0:
                negative += 1
            else:
                local_values[index] = int(value) if value.is_integer() else value
        expected = calendar.monthrange(2024, month)[1] * 24
        if len(seen) - first_count != expected or summaries != 3:
            raise ValueError(f"Month {month}: incomplete source labels or unexpected summary rows")
        summary_rows += summaries
        audit_months.append({"month": month, "observations": expected, "summaryRowsExcluded": summaries,
            "firstSourceLabel": min(month_labels), "lastSourceLabel": max(month_labels),
            "bytes": len(raw), "sha256": metadata["sha256"]})
    if len(seen) != HOURS:
        raise ValueError("Provincial source does not include all original 2024 local-year labels")
    utc_values = local_values[9:] + [None] * 9
    local_summary, utc_summary = summarize(local_values), summarize(utc_values)
    if not local_summary["eligibleForSeasonalComparison"] or not utc_summary["eligibleForSeasonalComparison"]:
        raise ValueError("Provincial source does not meet annual/seasonal capture selection: "
                         + json.dumps({"local": local_summary, "utc": utc_summary}, ensure_ascii=True))
    time_convention = {"source_timezone": "Asia/Seoul", "source_utc_offset_minutes": 540,
        "source_label_field": "dataDt", "source_label_format": "YYYYMMDDHH (00–23)",
        "source_first_label": min(labels), "source_last_label": max(labels),
        "hour_interval_semantics": "Original provincial JSON dataDt labels 00–23 are preserved without a one-hour shift. The province's public page adds one to display those observations as hours 01–24.",
        "utc_conversion": "Subtract nine hours from each original dataDt local label. No daylight-saving time in Seoul/Pyeongtaek in 2024.",
        "interpretation_limit": "The public page exposes the display's +1-hour convention, but a separate physical interval-start/end dictionary was not located. Data are grouped using the source's original 00–23 day labels, preserving each source day's 24 observations.",
        "evidence": PAGE,
        "utc_boundary": "Original local-year first nine hours precede UTC2024; the final nine UTC2024 hours need the following local year's data and remain null."}
    gap_note = f"August capture is {local_summary['monthlyCapture'][7]['capturePercent']:.3f}%, with a {local_summary['longestMissingRunHours']}-hour missing run; summer still passes the 75% seasonal rule."
    zero_note = f"The source reports {local_summary['zeroValuesRetained']} numeric zeros, including a {local_summary['longestZeroRunHours']}-hour run; these are retained and have no per-reading QA flags or detection-limit metadata."
    qa = "Provincial raw hourly observations; may differ from national final-confirmed data. Original dataDt labels 00–23 are preserved; the provincial page displays them as 01–24. " + gap_note + " " + zero_note
    quality = {key: value for key, value in utc_summary.items() if key not in ("monthlyCapture", "seasonCapture")}
    quality.update({"qaStatus": qa, "qualityFlagsAvailable": False,
        "ratificationStatus": "Raw provincial measurements; no NIER final-ratification claim.",
        "missingTreatment": "Missing source tokens, nonfinite/nonnumeric/negative readings and unavailable UTC boundary hours are null. Numeric zero retained; no interpolation or imputation.",
        "negativeReadingsExcluded": negative, "nonFiniteReadingsExcluded": nonfinite,
        "nonnumericReadingsExcluded": nonnumeric, "sourceRows": len(seen),
        "sourceSummaryRowsExcluded": summary_rows, "sourceMissingTokens": dict(missing_tokens),
        "outOfPeriodReadings": 9, "utcBoundaryMissingHours": 9, "duplicateHours": 0,
        "conflictingDuplicateHours": 0, "nonHourlyReadingsExcluded": 0,
        "license": LICENSE, "licenseEvidence": CATALOG, "licenseBasis": LICENSE_BASIS,
        "spatialScope": "One urban-air monitor, Songbuk-dong, Pyeongtaek; not a citywide average.",
        "documentedMaintenance": {"fromSourceDate": "2024-08-16", "throughSourceDate": "2024-08-30",
            "reason": "Station operation stopped after cooling-system failure",
            "source": "https://www.airkorea.or.kr/web/board/1/956/?pMENU_NO=197&page=11"},
        "selectionReason": "Identified Pyeongtaek urban monitor with at least 75% valid hours in the year and each meteorological season; no concentration-based selection."})
    sources = [{**metadata, "provider": "Gyeonggi Institute of Health and Environment",
                "attribution": ATTRIBUTION, "license": LICENSE, "licenseEvidence": CATALOG,
                "catalogUrl": PROVINCIAL_CATALOG, "licenseBasis": LICENSE_BASIS} for _, metadata in responses]
    record = {"schemaVersion": 1, "id": "pyeongtaek", "city": "Pyeongtaek", "year": 2024,
        "label": "Pyeongtaek · Songbuk-dong", "pollutant": "PM2.5", "units": "µg/m³",
        "timeZone": "Asia/Seoul", "standardOffsetMinutes": 540,
        "station": {"id": STATION_ID, "name": "Songbuk-dong", "sourceName": "송북동",
            "provider": "Gyeonggi Institute of Health and Environment", "type": "Urban-air monitoring station (도시대기)", "url": PAGE},
        "startUtc": "2024-01-01T00:00:00Z", "intervalMinutes": 60,
        "periodBasis": "UTC calendar year; original provincial local-year data also retained in localYear",
        "timeConvention": time_convention, "values": utc_values, "monthlyCapture": utc_summary["monthlyCapture"],
        "quality": quality, "sources": sources,
        "localYear": {"year": 2024, "startUtc": "2023-12-31T15:00:00Z", "intervalMinutes": 60,
            "values": local_values, "validHours": local_summary["validHours"], "capturePercent": local_summary["capturePercent"]},
        "preparedAtUtc": datetime.now(timezone.utc).isoformat()}
    audit = {"station": record["station"], "sourceUniqueHourLabels": len(seen),
        "firstSourceLabel": min(labels), "lastSourceLabel": max(labels),
        "monthlySourceFiles": audit_months, "localCalendarYear": local_summary,
        "commonUtcCalendarYear": utc_summary, "quality": quality,
        "timeConvention": time_convention, "sources": sources}
    return record, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch public provincial responses again")
    args = parser.parse_args()
    record, audit = prepare(acquire(refresh=args.refresh))
    path = ROOT / "data" / "comparisons" / "pyeongtaek-2024.json"
    write_json(path, record, compact=True)
    audit["output"] = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                       "sha256": sha256(path.read_bytes())}
    write_json(FOLDER / "quality-2024.json", audit)
    print(json.dumps({"output": audit["output"], "localYear": audit["localCalendarYear"],
                      "utcYear": audit["commonUtcCalendarYear"]}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
