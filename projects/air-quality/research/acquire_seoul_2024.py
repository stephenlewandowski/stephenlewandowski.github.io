"""Download and prepare Seoul's public 2024 hourly PM2.5 archive.

Standard library only. Raw ZIPs stay in data/seoul/.cache/ (Git-ignored).
The output preserves all 25 district monitors and adds an explicitly defined
equal-monitor mean. Source hour labels are preserved; see time_convention.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data" / "seoul"
SOURCE_PAGE = "https://data.seoul.go.kr/dataList/OA-2221/S/1/datasetView.do"
DOWNLOAD_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
POST_FIELDS = {"infId": "OA-2221", "seqNo": "", "seq": "35", "infSeq": "3"}
ARCHIVE_NAME = "서울시_기간별_시간평균_대기환경_정보_2024.zip"
PM25_FIELD = "초미세먼지(㎍/㎥)"
KST = timezone(timedelta(hours=9))
START = datetime(2024, 1, 1, tzinfo=KST)
END = datetime(2025, 1, 1, tzinfo=KST)
HOURS = int((END - START).total_seconds() // 3600)
MINIMUM_STATIONS = 20

ENGLISH_NAMES = {
    "중구": "Jung-gu", "종로구": "Jongno-gu", "용산구": "Yongsan-gu",
    "광진구": "Gwangjin-gu", "성동구": "Seongdong-gu", "중랑구": "Jungnang-gu",
    "동대문구": "Dongdaemun-gu", "성북구": "Seongbuk-gu", "도봉구": "Dobong-gu",
    "은평구": "Eunpyeong-gu", "서대문구": "Seodaemun-gu", "마포구": "Mapo-gu",
    "강서구": "Gangseo-gu", "구로구": "Guro-gu", "영등포구": "Yeongdeungpo-gu",
    "동작구": "Dongjak-gu", "관악구": "Gwanak-gu", "강남구": "Gangnam-gu",
    "서초구": "Seocho-gu", "송파구": "Songpa-gu", "강동구": "Gangdong-gu",
    "금천구": "Geumcheon-gu", "강북구": "Gangbuk-gu", "양천구": "Yangcheon-gu",
    "노원구": "Nowon-gu",
}


def write_json(path, content, compact=False):
    options = {"ensure_ascii": False, "allow_nan": False}
    options.update({"separators": (",", ":")} if compact else {"indent": 2})
    path.write_text(json.dumps(content, **options) + "\n", encoding="utf-8")


def download(cache, refresh=False):
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "2024.zip"
    record = cache / "download.json"
    if refresh or not target.exists():
        body = urllib.parse.urlencode(POST_FIELDS).encode("ascii")
        request = urllib.request.Request(DOWNLOAD_URL, data=body, headers={
            "User-Agent": "Mozilla/5.0 air-quality-comparison-research"})
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read(20_000_001)
            if len(raw) > 20_000_000 or not zipfile.is_zipfile(io.BytesIO(raw)):
                raise ValueError("Unexpected Seoul archive response")
            target.write_bytes(raw)
            write_json(record, {
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "response_date": response.headers.get("Date"),
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
            })
    if record.exists():
        fetch_metadata = json.loads(record.read_text(encoding="utf-8"))
    else:
        # A previously downloaded, inspected file can be reused without a new request.
        fetch_metadata = {
            "retrieved_at_utc": datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).isoformat(),
            "retrieval_time_basis": "filesystem modification time of the cached download",
        }
    return target.read_bytes(), fetch_metadata


def periods():
    months = defaultdict(list)
    seasons = defaultdict(list)
    names = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
             6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
    for index in range(HOURS):
        month = (START + timedelta(hours=index)).month
        months[f"2024-{month:02d}"].append(index)
        seasons[names[month]].append(index)
    return months, seasons


MONTHS, SEASONS = periods()


def summarize(values):
    valid = [value for value in values if value is not None]

    def captures(groups):
        result = {}
        for name, indexes in groups.items():
            count = sum(values[index] is not None for index in indexes)
            result[name] = {"valid_hours": count, "expected_hours": len(indexes),
                            "coverage_percent": round(100 * count / len(indexes), 3)}
        return result

    longest_gap = gap = 0
    for value in values:
        gap = gap + 1 if value is None else 0
        longest_gap = max(longest_gap, gap)
    return {
        "valid_hours": len(valid), "expected_hours": HOURS,
        "coverage_percent": round(100 * len(valid) / HOURS, 3),
        "minimum": min(valid) if valid else None, "maximum": max(valid) if valid else None,
        "mean": round(sum(valid) / len(valid), 4) if valid else None,
        "longest_missing_run_hours": longest_gap,
        "monthly": captures(MONTHS), "seasons": captures(SEASONS),
    }


def prepare(raw, fetch_metadata, destination):
    archive = zipfile.ZipFile(io.BytesIO(raw))
    members = [entry for entry in archive.infolist() if not entry.is_dir()]
    if len(members) != 1:
        raise ValueError(f"Expected one Seoul CSV, found {len(members)}")
    member = members[0]
    csv_bytes = archive.read(member)
    text = csv_bytes.decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(text))
    header = rows.fieldnames
    if PM25_FIELD not in header:
        raise ValueError("PM2.5 field missing")
    stations = {}
    observations = Counter()
    duplicate_examples = []
    blank_counts = Counter()
    invalid_counts = Counter()
    negative_counts = Counter()
    nonfinite_counts = Counter()
    unexpected_values = Counter()
    row_count = 0
    source_times = set()
    zero_count = 0
    for row in rows:
        row_count += 1
        stamp = row["측정일시"].strip()
        instant = datetime.strptime(stamp, "%Y%m%d%H%M").replace(tzinfo=KST)
        offset = (instant - START).total_seconds() / 3600
        if offset != int(offset) or not 0 <= offset < HOURS:
            raise ValueError(f"Timestamp outside hourly 2024 grid: {stamp}")
        index = int(offset)
        source_times.add(stamp)
        station_id = row["측정소코드"].strip()
        station_name = row["측정소명"].strip()
        if station_id not in stations:
            stations[station_id] = {
                "id": f"seoul-{station_id}", "kind": "station", "station_id": station_id,
                "name": ENGLISH_NAMES[station_name], "name_ko": station_name,
                "area_code": row["권역코드"], "area_name_ko": row["권역명"],
                "values": [None] * HOURS,
            }
        elif stations[station_id]["name_ko"] != station_name:
            raise ValueError(f"Station name changes for {station_id}")
        key = (station_id, index)
        observations[key] += 1
        token = row[PM25_FIELD].strip()
        value = None
        if not token:
            blank_counts[station_id] += 1
        else:
            try:
                number = float(token)
            except ValueError:
                invalid_counts[station_id] += 1
                unexpected_values[token] += 1
            else:
                if not math.isfinite(number):
                    nonfinite_counts[station_id] += 1
                elif number < 0:
                    negative_counts[station_id] += 1
                else:
                    value = int(number) if number.is_integer() else number
                    zero_count += value == 0
        if observations[key] > 1:
            duplicate_examples.append({"station_id": station_id, "source_time": stamp,
                                       "previous": stations[station_id]["values"][index], "new": value})
            # Do not silently choose between colliding observations.
            raise ValueError(f"Duplicate station-hour: {duplicate_examples[-1]}")
        stations[station_id]["values"][index] = value

    if HOURS != 8784 or len(stations) != 25 or len(source_times) != HOURS:
        raise ValueError("Unexpected Seoul calendar-year/station coverage")

    station_series = sorted(stations.values(), key=lambda station: station["name"])
    station_quality = {}
    for station in station_series:
        quality = summarize(station["values"])
        station_id = station["station_id"]
        present_rows = sum(1 for key in observations if key[0] == station_id)
        quality.update({"id": station["id"], "station_id": station_id, "name": station["name"],
                        "name_ko": station["name_ko"], "source_rows": present_rows,
                        "absent_rows": HOURS - present_rows,
                        "blank_values": blank_counts[station_id],
                        "negative_values_removed": negative_counts[station_id],
                        "nonnumeric_values_removed": invalid_counts[station_id],
                        "nonfinite_values_removed": nonfinite_counts[station_id]})
        station_quality[station_id] = quality
        station["coverage_percent"] = quality["coverage_percent"]
        station["valid_hours"] = quality["valid_hours"]
        station["eligible_for_network_mean"] = quality["coverage_percent"] >= 75 and all(
            item["coverage_percent"] >= 75 for item in quality["seasons"].values())

    eligible = [station for station in station_series if station["eligible_for_network_mean"]]
    if len(eligible) != 25:
        raise ValueError("A Seoul station failed 75% annual/seasonal eligibility; review the network rule")
    counts, network = [], []
    for index in range(HOURS):
        values = [station["values"][index] for station in eligible if station["values"][index] is not None]
        counts.append(len(values))
        network.append(round(sum(values) / len(values), 2) if len(values) >= MINIMUM_STATIONS else None)
    network_series = {
        "id": "seoul-network-mean", "kind": "network_mean", "name": "Mean of Seoul's 25 district monitors",
        "values": network, "station_ids": [station["station_id"] for station in eligible],
        "minimum_stations_per_hour": MINIMUM_STATIONS, "station_counts": counts,
        "coverage_percent": summarize(network)["coverage_percent"],
        "valid_hours": sum(value is not None for value in network),
        "description": "Unweighted mean of valid hourly concentrations at the 25 district monitors; at least 20 monitors required per hour. Each included monitor has at least 75% valid hours in the year and in every season. This is not a population-weighted exposure estimate.",
    }

    source = {
        "provider": "Seoul Metropolitan Government", "dataset_id": "OA-2221",
        "title": "Seoul hourly air-quality archive, 2024",
        "title_ko": "서울시 기간별 시간평균 대기환경 정보", "page_url": SOURCE_PAGE,
        "download_url": DOWNLOAD_URL, "download_method": "POST", "post_fields": POST_FIELDS,
        "archive_name": ARCHIVE_NAME, "archive_bytes": len(raw),
        "archive_sha256": hashlib.sha256(raw).hexdigest(),
        "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "file_modified_date_on_portal": "2025-11-07", "encoding": "UTF-8 with BOM",
        "retrieved_at_utc": fetch_metadata["retrieved_at_utc"],
        "license": "KOGL Type 1 (attribution; commercial reuse and adaptation allowed)",
        "license_url": "https://www.kogl.or.kr/info/licenseType1.do",
        "attribution": "Source: Seoul Metropolitan Government, Seoul Open Data Plaza, OA-2221; 2024 hourly air-quality archive, modified 7 November 2025. Extracted and aggregated for this comparison.",
        "qa_status": "Archived municipal observations; final national ratification status is not supplied in this file.",
        "quality_flags_available": False,
    }
    time_convention = {
        "source_timezone": "Asia/Seoul", "source_utc_offset_minutes": 540,
        "source_label_field": "측정일시", "source_label_format": "YYYYMMDDHHmm",
        "source_first_label": min(source_times), "source_last_label": max(source_times),
        "hour_interval_semantics": "The portal describes hourly means but does not explicitly identify hour-start versus hour-end in the inspected metadata. Source labels are preserved without a one-hour shift.",
        "utc_conversion": "Subtract 9 hours from the source local label. No daylight-saving time in Seoul in 2024.",
        "interpretation_limit": "Use calendar/seasonal and rolling comparisons. Exact simultaneous-hour comparisons may have a one-hour convention offset until confirmed with the provider.",
    }
    output = {
        "schema_version": 1, "city": "Seoul", "city_id": "seoul", "year": 2024,
        "pollutant": "PM2.5", "unit": "µg/m³", "timezone": "Asia/Seoul",
        "utc_offset_minutes": 540, "start_local": START.isoformat(),
        "start_utc": START.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "end_local_exclusive": END.isoformat(), "step_seconds": 3600, "hours": HOURS,
        "default_series_id": network_series["id"], "source": source,
        "time_convention": time_convention, "series": [network_series, *station_series],
    }
    destination.mkdir(parents=True, exist_ok=True)
    series_path = destination / "hourly-2024.json"
    write_json(series_path, output, compact=True)
    quality = {
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(), "source": source,
        "time_convention": time_convention, "source_header": header,
        "expected_calendar_hours": HOURS, "source_unique_hour_labels": len(source_times),
        "station_count": len(station_series), "source_data_rows": row_count,
        "expected_station_hour_rows": HOURS * len(station_series),
        "absent_station_hour_rows": HOURS * len(station_series) - len(observations),
        "absent_station_hour_examples": [
            {"station_id": station["station_id"],
             "source_label": (START + timedelta(hours=index)).strftime("%Y%m%d%H%M")}
            for station in station_series for index in range(HOURS)
            if (station["station_id"], index) not in observations
        ][:20],
        "duplicate_station_hour_rows": sum(count - 1 for count in observations.values()),
        "blank_pm25_values": sum(blank_counts.values()),
        "negative_values_removed": sum(negative_counts.values()),
        "nonnumeric_values_removed": sum(invalid_counts.values()),
        "nonfinite_values_removed": sum(nonfinite_counts.values()),
        "nonnumeric_tokens": dict(unexpected_values), "zero_values_retained": zero_count,
        "missing_rule": "Absent rows, blank tokens, nonnumeric or nonfinite values and negative concentrations become JSON null; retain numeric zero. No imputation, smoothing, clipping or arbitrary upper cutoff. All observed nonblank 2024 PM2.5 values were nonnegative integers.",
        "network_mean": {
            "id": network_series["id"], "definition": network_series["description"],
            "station_count_distribution": dict(sorted(Counter(counts).items())),
            "hours_below_minimum_monitor_count": [
                {"source_local_label": (START + timedelta(hours=index)).isoformat(),
                 "valid_station_count": count}
                for index, count in enumerate(counts) if count < MINIMUM_STATIONS
            ],
            "coverage": summarize(network),
        },
        "stations": station_quality,
        "output": {"path": "data/seoul/hourly-2024.json", "bytes": series_path.stat().st_size,
                   "sha256": hashlib.sha256(series_path.read_bytes()).hexdigest()},
    }
    write_json(destination / "quality-2024.json", quality)
    # Match comparison-city UTC calendar-year files. The municipal file ends at
    # 23:00 KST = 14:00 UTC on 31 December. Do not synthesize its last nine hours.
    utc_values = network[9:] + [None] * 9
    utc_counts = counts[9:] + [0] * 9
    utc_summary = summarize(utc_values)
    standardized = {
        "schemaVersion": 1, "id": "seoul", "city": "Seoul", "year": 2024,
        "pollutant": "PM2.5", "units": "µg/m³", "timeZone": "Asia/Seoul",
        "station": {
            "id": "seoul-network-mean", "name": "Mean of Seoul's 25 district monitors",
            "provider": "Seoul Metropolitan Government", "type": "Mean of 25 district monitors",
            "url": SOURCE_PAGE, "aggregation": network_series["description"],
            "minimumStationsPerHour": MINIMUM_STATIONS, "stationCount": len(eligible),
            "stationIds": network_series["station_ids"],
        },
        "startUtc": "2024-01-01T00:00:00Z", "intervalMinutes": 60,
        "periodBasis": "UTC calendar year; local times are available using the stated time zone",
        "timeConvention": time_convention,
        "values": utc_values, "stationCounts": utc_counts,
        "monthlyCapture": [{"month": int(name[-2:]), "expectedHours": item["expected_hours"],
                            "validHours": item["valid_hours"], "capturePercent": item["coverage_percent"]}
                           for name, item in utc_summary["monthly"].items()],
        "quality": {
            "expectedHours": HOURS, "validHours": utc_summary["valid_hours"],
            "capturePercent": utc_summary["coverage_percent"], "minimum": utc_summary["minimum"],
            "maximum": utc_summary["maximum"], "allMonthsPresent": all(item["valid_hours"] > 0 for item in utc_summary["monthly"].values()),
            "missingTreatment": "null; no interpolation or imputation; network mean requires at least 20 of 25 monitors",
            "negativeReadingsExcluded": sum(negative_counts.values()),
            "nonFiniteReadingsExcluded": sum(nonfinite_counts.values()),
            "outOfPeriodReadings": 9, "duplicateHours": 0, "conflictingDuplicateHours": 0,
            "nonHourlyReadingsExcluded": 0, "sourceRows": row_count,
            "sourceBlankConcentrations": sum(blank_counts.values()),
            "sourceAbsentStationHours": HOURS * len(station_series) - len(observations),
            "utcBoundaryMissingHours": 9,
            "outOfPeriodNote": "Nine network hours labelled 1 January 2024 00:00–08:00 KST fall in UTC 2023; the nine UTC hours after 31 December 2024 14:00 are unavailable in this source file and remain null.",
            "qaStatus": source["qa_status"], "qualityFlagsAvailable": False,
            "longestMissingRunHours": utc_summary["longest_missing_run_hours"],
        },
        "sources": [{"url": DOWNLOAD_URL, "pageUrl": SOURCE_PAGE,
                     "method": "POST", "postFields": POST_FIELDS,
                     "sha256": source["archive_sha256"], "bytes": len(raw),
                     "downloadedAtUtc": source["retrieved_at_utc"], "fileModifiedDate": "2025-11-07",
                     "license": source["license"], "attribution": source["attribution"]}],
        "preparedAtUtc": quality["prepared_at_utc"],
    }
    standardized_path = destination / "seoul-2024.json"
    write_json(standardized_path, standardized, compact=True)
    quality["standardized_utc_output"] = {
        "path": "data/seoul/seoul-2024.json", "bytes": standardized_path.stat().st_size,
        "sha256": hashlib.sha256(standardized_path.read_bytes()).hexdigest(),
        "coverage": utc_summary,
    }
    write_json(destination / "quality-2024.json", quality)
    print(json.dumps({"city": "Seoul", "rows": row_count, "stations": len(station_series),
                      "source_sha256": source["archive_sha256"],
                      "output": quality["output"], "network": summarize(network),
                      "station_coverage_range_percent": [min(item["coverage_percent"] for item in station_quality.values()),
                                                         max(item["coverage_percent"] for item in station_quality.values())]},
                     ensure_ascii=True, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Download again, replacing the cached source")
    parser.add_argument("--output-dir", type=Path, default=DESTINATION)
    parser.add_argument("--cache-dir", type=Path, default=DESTINATION / ".cache")
    arguments = parser.parse_args()
    source_bytes, retrieval = download(arguments.cache_dir, arguments.refresh)
    prepare(source_bytes, retrieval, arguments.output_dir)
