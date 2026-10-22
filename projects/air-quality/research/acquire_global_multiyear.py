"""Extend the same measured PM2.5 monitors to 2023 and 2025.

Python standard library plus Rscript (LondonAir annual RData). Source downloads
are cached outside the website; source URLs, retrieval times and SHA256 hashes
are included in every derived record. No interpolation or monitor substitution.
Usage: python acquire_global_multiyear.py [london|beijing|los-angeles] [YEAR ...]
"""
from __future__ import annotations

import calendar
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'data'
CACHE = Path('C:/Projects/Public_GitHub/air-quality-comparison/research/extended')
AIRDATA = 'https://aqs.epa.gov/aqsweb/airdata/'
UTC = timezone.utc


def fetch(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.bin')
    if not target.exists():
        if url.startswith(AIRDATA + 'hourly_'):
            # EPA supports byte ranges. Smaller verified ranges avoid long idle
            # full-file responses on the public server; their ordered byte
            # concatenation is the original zip, not a transformed dataset.
            request = urllib.request.Request(url, method='HEAD', headers={'Range': 'bytes=0-0'})
            with urllib.request.urlopen(request, timeout=90) as response:
                size = int(response.headers['Content-Range'].rsplit('/', 1)[1])
            ranges = [(first, min(size - 1, first + 1024 * 1024 - 1)) for first in range(0, size, 1024 * 1024)]
            def read_range(bounds):
                first, last = bounds
                for attempt in range(4):
                    try:
                        request = urllib.request.Request(url, headers={'Range': f'bytes={first}-{last}'})
                        with urllib.request.urlopen(request, timeout=90) as response:
                            assert response.status == 206
                            assert response.headers['Content-Range'] == f'bytes {first}-{last}/{size}'
                            body = response.read()
                        assert len(body) == last - first + 1
                        return body
                    except Exception:
                        if attempt == 3: raise
                        time.sleep(2 ** attempt)
            with ThreadPoolExecutor(max_workers=8) as pool:
                pieces = list(pool.map(read_range, ranges))
            target.write_bytes(b''.join(pieces))
            assert target.stat().st_size == size
        else:
            download(url, target)
    return target.read_bytes(), {'url': url, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'bytes': target.stat().st_size, 'downloadedAtUtc': datetime.fromtimestamp(target.stat().st_mtime, UTC).isoformat()}


def download(url, target):
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'HistoricalAirQualityComparison/2.0'})
            temporary = target.with_suffix('.download')
            with urllib.request.urlopen(request, timeout=180) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            temporary.replace(target)
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def period(year):
    start = datetime(year, 1, 1, tzinfo=UTC)
    return start, int((datetime(year + 1, 1, 1, tzinfo=UTC) - start).total_seconds() // 3600)


def coverage(values, year):
    start, hours = period(year)
    months, offset = [], 0
    for month in range(1, 13):
        expected = calendar.monthrange(year, month)[1] * 24
        valid = sum(v is not None for v in values[offset:offset + expected])
        months.append({'month': month, 'expectedHours': expected, 'validHours': valid,
            'capturePercent': round(valid / expected * 100, 3)})
        offset += expected
    seasons = {}
    for label, selected in [('Winter (Jan–Feb, Dec)', (1, 2, 12)), ('Spring (Mar–May)', (3, 4, 5)),
                            ('Summer (Jun–Aug)', (6, 7, 8)), ('Autumn (Sep–Nov)', (9, 10, 11))]:
        items = [v for i, v in enumerate(values) if (start + timedelta(hours=i)).month in selected]
        n = sum(v is not None for v in items)
        seasons[label] = {'expectedHours': len(items), 'validHours': n, 'capturePercent': round(n / len(items) * 100, 3)}
    return months, seasons


def prepare(slug, year, records, sources, extra, local_records=None):
    template = json.loads((OUT / f'{slug}-2024.json').read_text(encoding='utf-8'))
    start, hours = period(year)
    values = [None] * hours
    counts = {'negativeReadingsExcluded': 0, 'nonFiniteReadingsExcluded': 0,
              'nonHourlyReadingsExcluded': 0, 'outOfPeriodReadings': 0,
              'duplicateHours': 0, 'conflictingDuplicateHours': 0}
    for stamp, raw in sorted(records, key=lambda pair: pair[0]):
        elapsed = (stamp.astimezone(UTC) - start).total_seconds()
        if elapsed < 0 or elapsed >= hours * 3600:
            counts['outOfPeriodReadings'] += 1
            continue
        if elapsed % 3600:
            counts['nonHourlyReadingsExcluded'] += 1
            continue
        try:
            value = float(raw)
        except (ValueError, TypeError):
            counts['nonFiniteReadingsExcluded'] += 1
            continue
        if not math.isfinite(value):
            counts['nonFiniteReadingsExcluded'] += 1
            continue
        if value < 0:
            counts['negativeReadingsExcluded'] += 1
            continue
        index = int(elapsed // 3600)
        if values[index] is not None:
            counts['duplicateHours'] += 1
            if values[index] != round(value, 3):
                counts['conflictingDuplicateHours'] += 1
                raise ValueError(f'Conflicting duplicate {slug} {stamp}')
        values[index] = round(value, 3)
    valid = [v for v in values if v is not None]
    assert valid, f'No valid observations {slug} {year}'
    months, seasons = coverage(values, year)
    occupied = [i for i, value in enumerate(values) if value is not None]
    eligible = all(item['capturePercent'] >= 75 for item in seasons.values())
    gap = longest = 0
    for value in values:
        gap = gap + 1 if value is None else 0
        longest = max(gap, longest)
    result = {'schemaVersion': 1, 'id': slug, 'city': template['city'], 'year': year,
        'pollutant': 'PM2.5', 'units': 'µg/m³', 'timeZone': template['timeZone'],
        'station': template['station'], 'startUtc': start.isoformat().replace('+00:00', 'Z'),
        'intervalMinutes': 60, 'periodBasis': 'UTC calendar year; fixed local standard time is available in the application',
        'values': values, 'monthlyCapture': months, 'seasonalCapture': seasons,
        'quality': {'expectedHours': hours, 'validHours': len(valid),
            'capturePercent': round(len(valid) / hours * 100, 3), 'minimum': min(valid), 'maximum': max(valid),
            'allMonthsPresent': all(m['validHours'] > 0 for m in months),
            'minimumMonthlyCapturePercent': min(m['capturePercent'] for m in months),
            'longestMissingRunHours': longest, 'eligibleForSeasonalComparison': eligible,
            'seasonalEligibilityRule': 'At least 75% valid hourly readings in every UTC meteorological season',
            'exclusionReason': None if eligible else 'One or more seasons have less than 75% valid hourly readings; available observations are retained',
            'missingTreatment': 'null; no interpolation, imputation, or substitution of a different monitor',
            'sourcePrecisionNote': 'Concentrations serialized to three decimal places',
            'firstValidUtc': (start + timedelta(hours=occupied[0])).isoformat().replace('+00:00', 'Z'),
            'lastValidUtc': (start + timedelta(hours=occupied[-1])).isoformat().replace('+00:00', 'Z'),
            'spatialScope': 'One monitoring location; not a citywide or population-weighted exposure estimate',
            **counts, **extra},
        'sources': sorted(sources, key=lambda s: s['url']), 'preparedAtUtc': datetime.now(UTC).isoformat()}
    if local_records is not None:
        # Source EPA files are indexed by local standard year, eight hours later
        # than UTC. Keep the genuine complete source year separately, without
        # inventing the first eight UTC hours from an unavailable adjacent file.
        local_start = start + timedelta(hours=8)
        local_values = [None] * hours
        for stamp, raw in local_records:
            index = int((stamp - local_start).total_seconds() // 3600)
            if 0 <= index < hours and float(raw) >= 0:
                assert local_values[index] is None
                local_values[index] = round(float(raw), 3)
        result['standardOffsetMinutes'] = -480
        result['localYear'] = {'startUtc': local_start.isoformat().replace('+00:00', 'Z'),
            'intervalMinutes': 60, 'timeBasis': f'PST fixed local standard time, {year} calendar year',
            'values': local_values, 'expectedHours': hours,
            'validHours': sum(v is not None for v in local_values)}
        result['timeConvention'] = {'source_timezone': 'America/Los_Angeles',
            'source_utc_offset_minutes': -480, 'source_label_field': 'Date GMT + Time GMT',
            'hour_interval_semantics': 'EPA defines hourly timestamps as the beginning of sampling; local fields use fixed local standard time (PST, UTC−8).',
            'utc_conversion': 'Use supplied Date GMT + Time GMT; every row checked against local timestamp plus 8 hours.',
            'source_first_local_label': f'{year}-01-01T00:00', 'source_last_local_label': f'{year}-12-31T23:00',
            'documentation': AIRDATA + 'FileFormats.html'}
    path = OUT / f'{slug}-{year}.json'
    path.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    audit = {'file': path.name, 'outputSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'quality': result['quality'], 'monthlyCapture': months, 'seasonalCapture': seasons,
             'sources': result['sources']}
    (BASE / 'research' / f'{slug.upper().replace("-", "_")}_{year}_AUDIT.json').write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'file': path.name, 'quality': result['quality'], 'monthlyCapture': months}, ensure_ascii=False), flush=True)
    return result


def london(year):
    raw, source = fetch(f'https://londonair.org.uk/r_data/HP1_{year}.RData')
    path = CACHE / f'HP1_{year}.RData'
    path.write_bytes(raw)
    target = CACHE / f'HP1_{year}.csv'
    code = (f'load("{path.as_posix()}"); stopifnot("pm25" %in% names(x)); '
        'd <- data.frame(timestamp=format(x$date,tz="GMT",format="%Y-%m-%dT%H:%M:%SZ"),value=x$pm25); '
        f'write.csv(d,file="{target.as_posix()}",row.names=FALSE,na=""); cat(paste(names(x),collapse=","))')
    decoded = subprocess.run([shutil.which('Rscript') or r'C:/Program Files/R/R-4.6.1/bin/Rscript.exe', '--vanilla', '-e', code],
                             capture_output=True, text=True, check=True)
    records = [(datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')), row['value'])
               for row in csv.DictReader(io.StringIO(target.read_text(encoding='utf-8')))]
    return prepare('london', year, records, [source], {
        'sourceTimestamps': 'Annual RData POSIXct instants converted to GMT, following openair::importImperial(); no summer-time shift',
        'license': 'Open Government Licence v2; London Air Quality Network / Imperial College London',
        'licenseDocumentation': 'https://api.erg.ic.ac.uk/AirQuality/Information/Documentation/pdf',
        'sourceDocumentation': 'https://github.com/openair-project/openair/blob/main/R/importImperial.R',
        'sourceFields': decoded.stdout.strip().split(','), 'sourceQualityFlagsAvailable': False,
        'ratificationStatus': 'Not provided in the annual RData archive; no ratification claim is made',
        'selectionReason': 'Same HP1 urban-background monitor retained across years'})


def archive_keys(year):
    url = 'https://openaq-data-archive.s3.amazonaws.com/?' + urllib.parse.urlencode({
        'list-type': '2', 'prefix': f'records/csv.gz/locationid=8833/year={year}/', 'max-keys': 1000})
    raw, source = fetch(url)
    tree = ET.fromstring(raw)
    ns = {'s': 'http://s3.amazonaws.com/doc/2006-03-01/'}
    assert tree.findtext('s:IsTruncated', namespaces=ns) == 'false'
    return [item.text for item in tree.findall('s:Contents/s:Key', ns)], source


def beijing(year):
    keys, source = archive_keys(year)
    sources = [source]
    for adjacent, suffix in ((year - 1, f'{year-1}1231.csv.gz'), (year + 1, f'{year+1}0101.csv.gz')):
        extras, listing = archive_keys(adjacent)
        sources.append(listing)
        keys.extend(key for key in extras if key.endswith(suffix))
    records, sensors, units, coordinates = [], set(), set(), set()
    def day(key):
        raw, provenance = fetch('https://openaq-data-archive.s3.amazonaws.com/' + urllib.parse.quote(key, safe='/='))
        return list(csv.DictReader(io.StringIO(gzip.decompress(raw).decode('utf-8-sig')))), provenance
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in as_completed([pool.submit(day, key) for key in keys]):
            rows, provenance = future.result()
            sources.append(provenance)
            for row in rows:
                if row['parameter'] != 'pm25':
                    continue
                sensors.add(row['sensors_id']); units.add(row['units'])
                coordinates.add((float(row['lat']), float(row['lon'])))
                records.append((datetime.fromisoformat(row['datetime']), row['value']))
    assert sensors == {'25754'}, sensors
    assert coordinates == {(39.953352, 116.466258)}, coordinates
    assert units <= {'µg/m³', 'ug/m3', 'µg/m3'}, units
    return prepare('beijing', year, records, sources, {
        'archiveObjects': len(keys), 'sourceUnitStrings': sorted(units),
        'sourceTimestamps': 'Offset-aware measurement timestamps retained at reported UTC hour without rounding',
        'license': 'US Public Domain as shown on the OpenAQ location page',
        'licenseDocumentation': 'https://explore.openaq.org/locations/8833',
        'sourceDocumentation': 'https://docs.openaq.org/aws/year-guide',
        'sourceQualityFlagsAvailable': False, 'ratificationStatus': 'Not supplied in archived AirNow/OpenAQ rows',
        'selectionReason': 'Same OpenAQ location 8833 and PM2.5 sensor 25754; gaps and the 2025 cessation retained',
        'sourceCoverageNote': ('Partial 2025 record: the same-monitor public archive ends on March 4. No April–December observations are available; no later values are imputed.' if year == 2025 else 'All seasons contain observations, but February has only 10.7% hourly capture and March 49.2%. Do not interpret the available-hour mean as a complete annual comparison.'),
        'qaStatus': ('Partial 2025 record through March 4; later months are missing, not zero. Source rows do not supply ratification or quality flags.' if year == 2025 else 'The same monitor has major winter/spring gaps in 2023. February has 10.7% and March 49.2% hourly capture. Source rows do not supply ratification or quality flags.'),
        'partialYearNote': ('The same-monitor public archive ends on 2025-03-04. Later months have no observations; this is not a complete annual comparison.' if year == 2025 else 'Gaps in the same-monitor archive are retained; consult monthly and seasonal coverage.')})


def epa_rows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        # Reading the entire CSV below verifies its ZIP CRC automatically.
        assert len(archive.namelist()) == 1
        member = next(name for name in archive.namelist() if name.lower().endswith('.csv'))
        with archive.open(member) as binary, io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as text:
            header = next(text)
            selected = [line for line in text if line.startswith(('"06","037","1103",', '06,037,1103,'))]
    return list(csv.DictReader(io.StringIO(header + ''.join(selected))))


def los_angeles(year):
    with ThreadPoolExecutor(max_workers=2) as pool:
        datasets = list(pool.map(fetch, [AIRDATA + f'hourly_88101_{year}.zip', AIRDATA + f'annual_conc_by_monitor_{year}.zip']))
    hourly, annual_rows = [epa_rows(raw) for raw, source in datasets]
    selected = [row for row in hourly if row['Parameter Code'] == '88101' and row['POC'] == '3']
    annual = [row for row in annual_rows if row['Parameter Code'] == '88101' and row['POC'] == '3' and row['Sample Duration'] == '1 HOUR']
    assert selected and len(annual) == 1
    assert {row['Method Code'] for row in selected} == {'170'}
    assert {row['Method Type'] for row in selected} == {'FEM'}
    assert {row['Units of Measure'] for row in selected} == {'Micrograms/cubic meter (LC)'}
    assert {(float(row['Latitude']), float(row['Longitude'])) for row in selected} == {(34.06659, -118.22688)}
    assert {row['Qualifier'] for row in selected} <= {'', 'IH', 'IJ', 'IT', 'J'}, 'New qualifier requires explicit review'
    assert int(annual[0]['Observation Count']) == len(selected)
    records, flagged, negatives, stamps = [], [], [], set()
    for row in selected:
        stamp = datetime.fromisoformat(row['Date GMT'] + 'T' + row['Time GMT']).replace(tzinfo=UTC)
        local = datetime.fromisoformat(row['Date Local'] + 'T' + row['Time Local']).replace(tzinfo=UTC)
        assert stamp == local + timedelta(hours=8)
        assert stamp not in stamps and stamp.minute == 0 and stamp.second == 0
        stamps.add(stamp)
        value = float(row['Sample Measurement'])
        assert math.isfinite(value)
        records.append((stamp, value))
        detail = {'utc': stamp.isoformat().replace('+00:00', 'Z'), 'value': value, 'qualifier': row['Qualifier']}
        if row['Qualifier']: flagged.append(detail)
        if value < 0: negatives.append(detail)
    raw_path = BASE / 'research' / f'EPA_LOS_ANGELES_{year}_SELECTED.csv.gz'
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text, fieldnames=list(selected[0])); writer.writeheader(); writer.writerows(selected)
    raw_path.write_bytes(gzip.compress(text.getvalue().encode('utf-8'), mtime=0))
    evidence = {'annualHourlySummary': annual[0], 'flaggedObservations': flagged,
        'excludedNegativeObservations': negatives, 'rawExtractSha256': hashlib.sha256(raw_path.read_bytes()).hexdigest()}
    (BASE / 'research' / f'EPA_LOS_ANGELES_{year}_SOURCE_AUDIT.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    return prepare('los-angeles', year, records, [source for raw, source in datasets], {
        'sourceTimestamps': 'EPA Date GMT + Time GMT retained; checked against PST fixed local standard timestamp plus eight hours',
        'license': 'Public domain US EPA AQS monitoring data',
        'licenseDocumentation': 'https://www.epa.gov/outdoor-air-quality-data/do-i-need-request-permission-use-monitoring-data-and-graphics-airdata',
        'certificationStatus': annual[0]['Certification Indicator'],
        'certificationEvidence': f'annual_conc_by_monitor_{year}.zip; 06-037-1103/88101/POC3/1HOUR',
        'qaStatus': (f'EPA annual hourly summary: {annual[0]["Certification Indicator"]}. The app excludes negative concentrations and retains informational event flags. '
            + ('South Coast AQMD requests that POC 3 2025 not be compared to the NAAQS after failed comparability testing. Use these measured data for exploratory exposure comparisons, not an official regulatory assessment.' if year == 2025 else 'The site primary regulatory monitor is daily FRM POC 1; this same-monitor hourly POC 3 series is retained for exploratory exposure comparison.')),
        'sourceQualityFlagsAvailable': True, 'sourceQualifiers': dict(Counter(row['Qualifier'] or '(none)' for row in selected)),
        'qualifierDefinitions': {'IH': {'meaning': 'Fireworks', 'type': 'Informational Only'},
            'IJ': {'meaning': 'High Winds', 'type': 'Informational Only'},
            'IT': {'meaning': 'Wildfire-U. S.', 'type': 'Informational Only'},
            'J': {'meaning': 'Construction', 'type': 'Informational Only'}},
        'qualifierDocumentation': 'https://aqs.epa.gov/aqsweb/documents/codetables/qualifiers.html',
        'sampleDuration': '1 HOUR', 'selectionReason': 'Same site 06-037-1103, parameter 88101, POC 3, continuous FEM method 170 retained across years',
        'eventTreatment': 'Retain IH fireworks, IJ high winds, IT US wildfire and J construction observations, which EPA classifies as informational. Exclude negative reported concentrations under the application rule; original source rows remain in the research extract.',
        'regulatoryInterpretation': ('The July 2026 South Coast AQMD comparability appendix requests that this POC 3 2025 series not be compared to the NAAQS after its 2023–2025 bias assessment. It is retained for exploratory exposure comparison, not as an official regulatory design value.' if year == 2025 else 'POC 3 is an hourly FEM; the site daily FRM POC 1 is its primary monitor. These exploratory hourly comparisons do not reproduce official regulatory design values.'),
        'regulatoryComparisonExcluded': year == 2025,
        'regulatoryDocumentation': 'https://www.aqmd.gov/docs/default-source/clean-air-plans/air-quality-monitoring-network-plan/aaqmnp-appendix-cA4ED7731453B.pdf',
        'utcBoundaryMissingHours': 8,
        'boundaryNote': f'EPA file indexed by local standard {year}; first eight UTC-year hours are not in this file and remain null. Genuine localYear is retained separately.'}, local_records=records)


if __name__ == '__main__':
    city = sys.argv[1] if len(sys.argv) > 1 else 'london'
    years = list(map(int, sys.argv[2:])) or [2023, 2025]
    job = {'london': london, 'beijing': beijing, 'los-angeles': los_angeles}[city]
    for year in years:
        job(year)
