"""Package the audited Seoul district series on their original local-year grid.

Standard library only; no downloads or source mutations. The source directory
must contain data/seoul/{hourly-2024.json,quality-2024.json,.cache/2024.zip}.
The archive and prepared-file hashes are checked before packaging. Run from any
directory; --source-root defaults to the sibling air-quality-comparison project.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import gzip
import hashlib
import json
import math
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "projects" / "air-quality" / "data" / "seoul-stations-2024.json"
HOURS = 8784
STATION_COUNT = 25
START_UTC = "2023-12-31T15:00:00Z"
START_LOCAL = datetime(2024, 1, 1)
SEASON_MONTHS = {"winter": (1, 2, 12), "spring": (3, 4, 5),
                 "summer": (6, 7, 8), "autumn": (9, 10, 11)}
MONTHS = [(START_LOCAL + timedelta(hours=index)).month for index in range(HOURS)]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def valid_values(values, label):
    require(isinstance(values, list) and len(values) == HOURS,
            f"{label}: expected {HOURS} hourly values")
    require(all(value is None or type(value) in (int, float)
                and math.isfinite(value) and value >= 0 for value in values),
            f"{label}: values must be finite, nonnegative numbers or null")


def count_metadata(series, quality, label):
    values = series["values"]
    valid_values(values, label)
    valid_hours = sum(value is not None for value in values)
    capture = round(100 * valid_hours / HOURS, 3)
    require(series["valid_hours"] == quality["valid_hours"] == valid_hours,
            f"{label}: valid-hour metadata differs from the values")
    require(series["coverage_percent"] == quality["coverage_percent"] == capture,
            f"{label}: capture metadata differs from the values")
    require(quality["expected_hours"] == HOURS,
            f"{label}: expected-hour metadata differs")
    for season, months in SEASON_MONTHS.items():
        selected = [value for value, month in zip(values, MONTHS) if month in months]
        season_valid = sum(value is not None for value in selected)
        season_capture = round(100 * season_valid / len(selected), 3)
        recorded = quality["seasons"][season]
        require(recorded["expected_hours"] == len(selected)
                and recorded["valid_hours"] == season_valid
                and recorded["coverage_percent"] == season_capture,
                f"{label}: {season} capture metadata differs from the values")
        require(season_capture >= 75, f"{label}: {season} capture is below 75%")
    require(capture >= 75, f"{label}: annual capture is below 75%")
    return {"validHours": valid_hours, "capturePercent": capture}


def package(source_root):
    folder = source_root / "data" / "seoul"
    hourly_bytes = (folder / "hourly-2024.json").read_bytes()
    hourly = json.loads(hourly_bytes)
    quality = json.loads((folder / "quality-2024.json").read_text(encoding="utf-8"))
    deployed = json.loads((DESTINATION.parent / "seoul-2024.json").read_text(encoding="utf-8"))
    source = hourly["source"]
    require(source == quality["source"], "Prepared source metadata differs between files")
    require(sha256(hourly_bytes) == quality["output"]["sha256"],
            "Prepared hourly file does not match the quality audit hash")
    require(len(hourly_bytes) == quality["output"]["bytes"],
            "Prepared hourly file does not match the quality audit byte count")
    archive_bytes = (folder / ".cache" / "2024.zip").read_bytes()
    archive_sha256 = sha256(archive_bytes)
    require(archive_sha256 == source["archive_sha256"]
            == deployed["sources"][0]["sha256"], "Source archive SHA-256 differs")
    require(len(archive_bytes) == source["archive_bytes"]
            == deployed["sources"][0]["bytes"], "Source archive byte count differs")
    with zipfile.ZipFile(folder / ".cache" / "2024.zip") as archive:
        members = [entry for entry in archive.infolist() if not entry.is_dir()]
        require(len(members) == 1, "Expected one source CSV in the archive")
        require(sha256(archive.read(members[0])) == source["csv_sha256"],
                "Source CSV SHA-256 differs")

    require(hourly["year"] == 2024 and hourly["hours"] == HOURS
            and hourly["step_seconds"] == 3600 and hourly["pollutant"] == "PM2.5"
            and hourly["unit"] == "µg/m³" and hourly["timezone"] == "Asia/Seoul"
            and hourly["start_utc"] == START_UTC
            and hourly["start_local"] == "2024-01-01T00:00:00+09:00"
            and hourly["end_local_exclusive"] == "2025-01-01T00:00:00+09:00",
            "Unexpected Seoul pollutant, calendar or time grid")
    require(hourly["time_convention"] == quality["time_convention"]
            == deployed["timeConvention"], "Time-label conventions differ")
    require(quality["station_count"] == STATION_COUNT
            and quality["expected_calendar_hours"] == HOURS
            and quality["source_unique_hour_labels"] == HOURS
            and quality["duplicate_station_hour_rows"] == 0,
            "Unexpected source count metadata")

    networks = [series for series in hourly["series"] if series["kind"] == "network_mean"]
    stations = [series for series in hourly["series"] if series["kind"] == "station"]
    require(len(hourly["series"]) == 26 and len(networks) == 1
            and len(stations) == STATION_COUNT, "Expected one network and 25 district series")
    ids = [station["id"] for station in stations]
    station_ids = [station["station_id"] for station in stations]
    require(len(set(ids)) == STATION_COUNT and len(set(station_ids)) == STATION_COUNT,
            "Duplicate district identifiers")
    require(set(station_ids) == set(quality["stations"]), "District IDs differ from the audit")
    packaged_stations = []
    for station in stations:
        label = station["id"]
        audit = quality["stations"][station["station_id"]]
        require(station["id"] == f"seoul-{station['station_id']}" == audit["id"]
                and station["name"] == audit["name"]
                and station["name_ko"] == audit["name_ko"],
                f"{label}: station identity differs from the audit")
        metadata = count_metadata(station, audit, label)
        require(station["eligible_for_network_mean"] is True,
                f"{label}: source does not mark this station eligible")
        require(audit["source_rows"] + audit["absent_rows"] == HOURS,
                f"{label}: source row-count metadata differs")
        packaged = {"id": station["id"], "name": station["name"],
                    "sourceName": station["name_ko"], "sourceStationId": station["station_id"],
                    "values": station["values"], **metadata}
        # Preserve coordinates only if supplied by the audited source.
        for coordinate in ("latitude", "longitude"):
            if coordinate in station:
                packaged[coordinate] = station[coordinate]
        packaged_stations.append(packaged)

    network = networks[0]
    require(network["station_ids"] == station_ids == deployed["station"]["stationIds"],
            "Network monitor identities or order differ")
    require(network["minimum_stations_per_hour"] == 20
            == deployed["station"]["minimumStationsPerHour"],
            "Unexpected network minimum monitor count")
    counts = [sum(station["values"][index] is not None for station in stations)
              for index in range(HOURS)]
    require(network["station_counts"] == counts, "Network monitor counts differ from district values")
    for index, count in enumerate(counts):
        expected = round(sum(station["values"][index] for station in stations
                             if station["values"][index] is not None) / count, 2) if count >= 20 else None
        require(network["values"][index] == expected,
                f"Network mean differs from source district values at hour {index}")
    network_metadata = count_metadata(network, quality["network_mean"]["coverage"], network["id"])
    require({str(key): count for key, count in sorted(Counter(counts).items())}
            == quality["network_mean"]["station_count_distribution"],
            "Network monitor count distribution differs from the audit")
    require(network["values"][9:] + [None] * 9 == deployed["values"]
            and counts[9:] + [0] * 9 == deployed["stationCounts"],
            "Existing UTC network file differs from the original local-year data")
    require(sum(audit["source_rows"] for audit in quality["stations"].values())
            == quality["source_data_rows"], "Total source row-count metadata differs")

    sources = [{**deployed["sources"][0], "provider": source["provider"],
                "datasetId": source["dataset_id"], "title": source["title"],
                "titleKo": source["title_ko"], "archiveName": source["archive_name"],
                "csvSha256": source["csv_sha256"], "licenseUrl": source["license_url"],
                "qaStatus": source["qa_status"],
                "qualityFlagsAvailable": source["quality_flags_available"]}]
    result = {"schemaVersion": 1, "city": "Seoul", "year": 2024,
              "pollutant": "PM2.5", "units": "µg/m³", "timeZone": "Asia/Seoul",
              "startUtc": START_UTC, "intervalMinutes": 60, "sources": sources,
              "timeConvention": hourly["time_convention"],
              "network": {"id": network["id"], "name": network["name"],
                          "values": network["values"], "stationCounts": counts,
                          "stationIds": ids, "minimumStationsPerHour": 20,
                          "definition": network["description"], **network_metadata},
              "stations": packaged_stations, "sourceSha256": archive_sha256}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT.parent / "air-quality-comparison")
    args = parser.parse_args()
    result = package(args.source_root)
    raw = (json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
           + "\n").encode("utf-8")
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(raw)
    print(json.dumps({"output": str(DESTINATION), "bytes": len(raw),
                      "gzipBytes": len(gzip.compress(raw, mtime=0)),
                      "sha256": sha256(raw), "sourceSha256": result["sourceSha256"],
                      "stationCount": len(result["stations"]),
                      "stationCapturePercentRange": [min(s["capturePercent"] for s in result["stations"]),
                                                     max(s["capturePercent"] for s in result["stations"])],
                      "networkValidHours": result["network"]["validHours"],
                      "networkCapturePercent": result["network"]["capturePercent"]}, indent=2))


if __name__ == "__main__":
    main()
