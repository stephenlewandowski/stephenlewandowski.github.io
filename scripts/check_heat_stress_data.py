"""Independently audit the packaged 2024 heat comparison against raw source files.

Uses only the Python standard library. This checks the published records,
provenance, coverage and retained driving inputs; the builder separately checks
its thermal-index calculations against upstream reference cases.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
HOURS = 8784
CITY_IDS = ['seoul', 'pyeongtaek', 'london', 'beijing', 'los-angeles']
METRICS = ['temperature', 'humidity', 'utci', 'wbgt', 'wbgtShade']
RAW_FIELDS = {
    'temperature': 'temperature_2m', 'humidity': 'relative_humidity_2m',
    'dewpoint': 'dew_point_2m', 'windSpeed10m': 'wind_speed_10m',
    'surfacePressure': 'surface_pressure', 'shortwaveRadiation': 'shortwave_radiation_instant',
    'directRadiation': 'direct_radiation_instant',
}
RANGES = {'temperature': (-60, 60), 'humidity': (0, 100), 'utci': (-80, 80),
          'wbgt': (-60, 65), 'wbgtShade': (-60, 65)}
SEASONS = {'Winter (Jan-Feb, Dec)': (1, 2, 12), 'Spring': (3, 4, 5),
           'Summer': (6, 7, 8), 'Autumn': (9, 10, 11)}
TIMES = [START + timedelta(hours=hour) for hour in range(HOURS)]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_record(path):
    raw = path.read_bytes()
    # Hash Git's LF-normalised bytes, matching the builder and public assets.
    assert b'\r\n' not in raw, f'{path.name}: packaged JSON must use LF newlines.'
    return json.loads(raw), digest(raw)


def audit(data_root, source_root):
    manifest, _ = read_record(data_root / 'manifest.json')
    sources = json.loads((source_root / 'open-meteo-provenance.json').read_text(encoding='utf-8'))
    by_id = {source['id']: source for source in sources['sources']}
    assert set(by_id) == set(CITY_IDS), 'Unexpected/missing raw-source city.'
    assert [record['id'] for record in manifest['records']] == CITY_IDS, 'Unexpected/missing packaged city.'
    assert manifest['year'] == 2024 and manifest['hours'] == HOURS
    assert manifest['intervalMinutes'] == 60 and manifest['startUtc'] == '2024-01-01T00:00:00Z'
    assert set(manifest['metrics']) == set(METRICS)
    assert manifest['validation']['passed'] is True, 'Builder reference checks not recorded.'
    report = {'passed': True, 'hoursPerCity': HOURS, 'cityHours': HOURS * len(CITY_IDS), 'cities': []}
    for entry in manifest['records']:
        city_id = entry['id']
        source = by_id[city_id]
        record_path = data_root / Path(entry['file']).name
        record, checksum = read_record(record_path)
        assert checksum == entry['sha256'], f'{city_id}: packaged SHA-256 mismatch.'
        assert entry['file'] == f'data/{city_id}-2024.json'
        assert record['id'] == city_id and record['year'] == 2024
        assert record['startUtc'] == manifest['startUtc'] and record['intervalMinutes'] == 60
        assert record['utcOffsetHours'] == entry['utcOffsetHours']
        assert record['latitude'] == source['requestedLatitude']
        assert record['longitude'] == source['requestedLongitude']
        assert record['civilTimezone'] == source['civilTimezone']
        assert record['source']['url'] == source['url']
        assert record['source']['retrievedAt'] == source['retrievedAt']
        raw_bytes = (source_root / 'raw' / source['file']).read_bytes()
        assert digest(raw_bytes) == source['sha256'] == entry['sourceSha256'] == record['source']['sha256']
        raw = json.loads(raw_bytes)
        assert raw['hourly']['time'] == [time.strftime('%Y-%m-%dT%H:%M') for time in TIMES]
        assert raw['utc_offset_seconds'] == 0
        for key, raw_key in [('gridLatitude', 'latitude'), ('gridLongitude', 'longitude'),
                             ('gridElevationMetres', 'elevation')]:
            assert record[key] == raw[raw_key], f'{city_id}: {key} mismatch.'
        assert set(record['values']) == set(METRICS)
        assert set(record['inputs']) == set(RAW_FIELDS) - {'temperature', 'humidity'}
        for field, raw_field in RAW_FIELDS.items():
            retained = record['values'].get(field, record['inputs'].get(field))
            original = raw['hourly'][raw_field]
            assert len(original) == len(retained) == HOURS, f'{city_id}/{field}: incomplete inputs.'
            assert retained == [round(value, 1) for value in original], f'{city_id}/{field}: input alteration.'
        diagnostics = record['diagnostics']
        assert diagnostics == entry['diagnostics']
        metric_results = {}
        for metric in METRICS:
            values = record['values'][metric]
            assert len(values) == HOURS, f'{city_id}/{metric}: incomplete array.'
            finite = [value for value in values if value is not None]
            assert all(type(value) in (int, float) and math.isfinite(value) for value in finite)
            lower, upper = RANGES[metric]
            assert all(lower <= value <= upper for value in finite), f'{city_id}/{metric}: implausible range.'
            seasonal = {}
            for season, months in SEASONS.items():
                selected = [value for time, value in zip(TIMES, values) if time.month in months]
                count = sum(value is not None for value in selected)
                if metric not in ['wbgt', 'wbgtShade']:
                    assert count / len(selected) >= .99, f'{city_id}/{metric}/{season}: insufficient coverage.'
                seasonal[season] = {'validHours': count, 'expectedHours': len(selected)}
            metric_results[metric] = {'validHours': len(finite), 'minimum': min(finite), 'maximum': max(finite),
                                      'seasons': seasonal}
        utci_missing = sum(value is None for value in record['values']['utci'])
        assert diagnostics['utciMissingHours'] == utci_missing
        assert diagnostics['utciOutsideDomainHours'] <= utci_missing
        for metric, prefix in [('wbgt', 'wbgt'), ('wbgtShade', 'wbgtShade')]:
            missing = sum(value is None for value in record['values'][metric])
            assert diagnostics[f'{prefix}MissingHours'] == missing
            assert (diagnostics[f'{prefix}NonconvergentHours']
                    + diagnostics[f'{prefix}OutsidePropertyFitHours']) == missing
        wind = raw['hourly']['wind_speed_10m']
        assert diagnostics['utciWindFloorHours'] == sum(
            value < .5 and result is not None for value, result in zip(wind, record['values']['utci']))
        assert diagnostics['wbgtWindFloorHours'] == sum(value < .62 for value in wind)
        assert diagnostics['subfreezingAirHours'] == sum(value < 0 for value in raw['hourly']['temperature_2m'])
        offset = timedelta(hours=record['utcOffsetHours'])
        # The archive is a complete UTC year. Local grouping shifts its edges;
        # reporting them makes partial local boundary days explicit.
        local_start = (TIMES[0] + offset).strftime('%Y-%m-%dT%H:%M')
        local_end = (TIMES[-1] + offset).strftime('%Y-%m-%dT%H:%M')
        report['cities'].append({'id': city_id, 'metrics': metric_results,
                                'firstLocalStandardHour': local_start,
                                'lastLocalStandardHour': local_end,
                                'utciWindFloorHours': diagnostics['utciWindFloorHours'],
                                'wbgtWindFloorHours': diagnostics['wbgtWindFloorHours']})
        print(f'{record["city"]}: hashes, 8,784 input hours and coverage accounting passed; '
              f'outdoor/shade WBGT valid hours {metric_results["wbgt"]["validHours"]}/'
              f'{metric_results["wbgtShade"]["validHours"]}; '
              f'local-standard span {local_start} to {local_end}.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=ROOT / 'projects' / 'heat-stress' / 'data')
    parser.add_argument('--source-root', type=Path, default=ROOT.parent / 'heat-stress-comparison' / 'research')
    parser.add_argument('--report', type=Path, help='Optionally save the full QA report outside the website.')
    args = parser.parse_args()
    report = audit(args.data_root, args.source_root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print('Passed: 43,920 city-hours checked against original sources; all reference checks recorded as passing.')
