"""Audit timestamp-aligned PM2.5/weather daily pairs without downloading data.

Uses only the standard library and the retained files from the two companion
projects. --update-manifest rebuilds provenance and expected coverage from those
files; otherwise every stored source checksum and coverage count must match.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'projects' / 'air-heat'
MANIFEST = PROJECT / 'data' / 'manifest.json'
CITY_IDS = ['seoul', 'pyeongtaek', 'london', 'beijing', 'los-angeles']
METRICS = ['temperature', 'humidity', 'utci', 'wbgt', 'wbgtShade']
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
HOURS = 8784
SEASONS = {'winter': (1, 2, 12), 'spring': (3, 4, 5),
           'summer': (6, 7, 8), 'autumn': (9, 10, 11)}


def read(path):
    """Hash canonical LF source bytes, matching the version-controlled assets."""
    raw = path.read_bytes().replace(b'\r\n', b'\n')
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def parse_time(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def daily_pairs(pm, heat, metric, offset_hours):
    """Independent calendar join; both means use the same >=18 valid hours.

    Source array extents, not their first/last nonmissing value, determine full
    calendar days. Local days outside 2024 and incomplete archive boundary days
    are omitted. No interpolation or threshold-based sparse-day exception.
    """
    pm_start, heat_start = parse_time(pm['startUtc']), parse_time(heat['startUtc'])
    assert pm['intervalMinutes'] == heat['intervalMinutes'] == 60
    assert pm_start.minute == heat_start.minute == 0
    pm_values, heat_values = pm['values'], heat['values'][metric]
    begin = max(pm_start, heat_start)
    end = min(pm_start + timedelta(hours=len(pm_values)),
              heat_start + timedelta(hours=len(heat_values)))
    offset = timedelta(hours=offset_hours)
    local_begin = begin + offset
    day = local_begin.replace(hour=0, minute=0, second=0, microsecond=0)
    if day < local_begin:
        day += timedelta(days=1)
    rows = []
    while day + timedelta(days=1) <= end + offset:
        if day.year == 2024:
            utc_begin = day - offset
            pm_index = int((utc_begin - pm_start).total_seconds() / 3600)
            heat_index = int((utc_begin - heat_start).total_seconds() / 3600)
            pairs = []
            pm_count = heat_count = 0
            for hour in range(24):
                y, x = pm_values[pm_index + hour], heat_values[heat_index + hour]
                pm_valid = finite(y) and y >= 0
                heat_valid = finite(x)
                pm_count += pm_valid
                heat_count += heat_valid
                if pm_valid and heat_valid:
                    pairs.append((x, y))
            eligible = len(pairs) >= 18
            rows.append({'date': day.strftime('%Y-%m-%d'), 'month': day.month,
                         'pmHours': pm_count, 'heatHours': heat_count,
                         'pairedHours': len(pairs), 'eligible': eligible,
                         'pmMean': sum(y for x, y in pairs) / len(pairs) if eligible else None,
                         'heatMean': sum(x for x, y in pairs) / len(pairs) if eligible else None})
        day += timedelta(days=1)
    return rows


def correlation(rows, within_month=False):
    rows = [row for row in rows if row['eligible']]
    if len(rows) < 3:
        return None
    groups = defaultdict(list)
    for row in rows:
        groups[row['month'] if within_month else 0].append(row)
    x_values, y_values = [], []
    for group in groups.values():
        x_mean = sum(row['heatMean'] for row in group) / len(group)
        y_mean = sum(row['pmMean'] for row in group) / len(group)
        for row in group:
            x_values.append(row['heatMean'] - x_mean)
            y_values.append(row['pmMean'] - y_mean)
    xy = sum(x * y for x, y in zip(x_values, y_values))
    xx = sum(x * x for x in x_values)
    yy = sum(y * y for y in y_values)
    return round(xy / math.sqrt(xx * yy), 8) if xx and yy else None


def coverage(rows):
    selected = [row for row in rows if row['eligible']]
    monthly = [sum(row['eligible'] and row['month'] == month for row in rows)
               for month in range(1, 13)]
    seasons = {name: {'completeDays': sum(row['month'] in months for row in rows),
                      'pairedEligibleDays': sum(row['eligible'] and row['month'] in months for row in rows)}
               for name, months in SEASONS.items()}
    return {'completeDays': len(rows),
            'pmEligibleDays': sum(row['pmHours'] >= 18 for row in rows),
            'heatEligibleDays': sum(row['heatHours'] >= 18 for row in rows),
            'pairedEligibleDays': len(selected),
            'expectedHours': len(rows) * 24,
            'pmHours': sum(row['pmHours'] for row in rows),
            'heatHours': sum(row['heatHours'] for row in rows),
            'pairedHours': sum(row['pairedHours'] for row in rows),
            'eligiblePairedHours': sum(row['pairedHours'] for row in selected),
            'monthlyPairedDays': monthly,
            'seasonPairedDays': seasons,
            'rawPearsonR': correlation(rows),
            'withinMonthPearsonR': correlation(rows, within_month=True)}


def build_manifest():
    pm_manifest, pm_manifest_hash = read(ROOT / 'projects/air-quality/data/manifest.json')
    heat_manifest, heat_manifest_hash = read(ROOT / 'projects/heat-stress/data/manifest.json')
    assert [row['id'] for row in pm_manifest['records']] == CITY_IDS
    assert [row['id'] for row in heat_manifest['records']] == CITY_IDS
    manifest = {
        'schemaVersion': 1, 'year': 2024,
        'period': {'from': '2024-01-01', 'through': '2024-12-31'},
        'dataKind': 'Measured PM2.5 paired with city-area gridded ERA5 weather estimates; no health outcomes or individual exposure data.',
        'checksumConvention': 'SHA-256 of retained UTF-8 source JSON with CRLF normalized to LF, matching Git/published assets.',
        'pairing': {
            'join': 'Exact reported UTC timestamp; source array indices are not assumed to align.',
            'defaultBasis': 'local', 'alternateBasis': 'utc',
            'localTime': 'Fixed local standard time; no daylight saving time.',
            'minimumPairedHoursPerDay': 18, 'hoursPerCompleteDay': 24,
            'dailyMeans': 'Both means use the same intersection of finite nonnegative PM2.5 and finite selected-weather values. Each thermal index is calculated hourly before the paired daily mean.',
            'periodSelection': 'Inclusive calendar-day labels in the chosen basis, restricted to 2024. A day must fall wholly within both retained source array extents.',
            'missing': 'No interpolation, imputation or replacement of missing/excluded values. Reported PM2.5 zeros remain valid.',
            'boundary': 'The weather archive spans a full UTC year. Nonzero-offset local calendar years have partial endpoint days; those fragments are excluded. Supplemental PM-only local-year values do not create missing weather hours.',
            'timestampLimit': 'Several PM providers do not explicitly resolve hour-start versus hour-end semantics. Source labels are preserved, so reported-hour pairing is not a verified physical overlap of sampling intervals.',
            'noRegulatoryRule': 'Ordinary >=18 shared hours; no EPA truncation, exceptional sparse-day rule or regulatory design-value calculation.',
        },
        'sourceManifests': [
            {'file': '../air-quality/data/manifest.json', 'sha256': pm_manifest_hash},
            {'file': '../heat-stress/data/manifest.json', 'sha256': heat_manifest_hash},
        ],
        'metrics': heat_manifest['metrics'],
        'records': [],
    }
    all_reports = {}
    for pm_entry, heat_entry in zip(pm_manifest['records'], heat_manifest['records']):
        city_id = pm_entry['id']
        pm_file = f'../air-quality/data/{city_id}-2024.json'
        heat_file = f'../heat-stress/data/{city_id}-2024.json'
        pm, pm_hash = read(PROJECT / pm_file)
        heat, heat_hash = read(PROJECT / heat_file)
        assert pm_hash == pm_entry['sha256'], f'{city_id}: PM source hash changed.'
        assert heat_hash == heat_entry['sha256'], f'{city_id}: weather source hash changed.'
        assert pm['id'] == heat['id'] == city_id
        assert pm['startUtc'] == heat['startUtc'] == '2024-01-01T00:00:00Z'
        assert len(pm['values']) == HOURS
        assert all(value is None or finite(value) and value >= 0 for value in pm['values'])
        assert set(heat['values']) == set(METRICS)
        assert all(len(heat['values'][metric]) == HOURS for metric in METRICS)
        for metric in METRICS:
            assert all(value is None or finite(value) for value in heat['values'][metric])
        counts = {}
        for basis in ['local', 'utc']:
            offset = heat['utcOffsetHours'] if basis == 'local' else 0
            counts[basis] = {metric: coverage(daily_pairs(pm, heat, metric, offset)) for metric in METRICS}
            for metric in ['temperature', 'humidity', 'utci']:
                assert all(row['pairedEligibleDays'] / row['completeDays'] >= .75
                           for row in counts[basis][metric]['seasonPairedDays'].values()), \
                    f'{city_id}/{basis}/{metric}: season below 75% paired-day coverage.'
        record = {
            'id': city_id, 'city': pm['city'], 'utcOffsetHours': heat['utcOffsetHours'],
            'pm': {'file': pm_file, 'sha256': pm_hash, 'startUtc': pm['startUtc'],
                   'intervalMinutes': 60, 'units': pm['units'], 'station': pm['station'],
                   'qaStatus': pm['quality'].get('qaStatus', pm['quality'].get('ratificationStatus'))},
            'heat': {'file': heat_file, 'sha256': heat_hash, 'startUtc': heat['startUtc'],
                     'intervalMinutes': 60, 'gridLatitude': heat['gridLatitude'],
                     'gridLongitude': heat['gridLongitude'], 'dataset': heat_manifest['dataset']},
            'expectedDailyPairs': counts,
        }
        manifest['records'].append(record)
        all_reports[city_id] = counts
        values = counts['local']
        print(f"{pm['city']}: local complete days {values['temperature']['completeDays']}; "
              f"temperature/UTCI pairs {values['temperature']['pairedEligibleDays']}/"
              f"{values['utci']['pairedEligibleDays']}; WBGT exposed/no-shortwave pairs "
              f"{values['wbgt']['pairedEligibleDays']}/{values['wbgtShade']['pairedEligibleDays']}.")
    supplement_file = '../air-quality/data/seoul-stations-2024.json'
    supplement, supplement_hash = read(PROJECT / supplement_file)
    assert supplement['startUtc'] == '2023-12-31T15:00:00Z'
    assert supplement['intervalMinutes'] == 60 and len(supplement['stations']) == 25
    seoul, _ = read(PROJECT / '../air-quality/data/seoul-2024.json')
    seoul_heat, _ = read(PROJECT / '../heat-stress/data/seoul-2024.json')
    assert supplement['network']['values'][9:] + [None] * 9 == seoul['values']
    assert len({station['id'] for station in supplement['stations']}) == 25
    district_reports = {}
    for station in supplement['stations']:
        assert len(station['values']) == HOURS
        assert all(value is None or finite(value) and value >= 0 for value in station['values'])
        pm_station = {**supplement, 'values': station['values']}
        district_reports[station['id']] = {
            basis: {metric: coverage(daily_pairs(pm_station, seoul_heat, metric, 9 if basis == 'local' else 0))
                    for metric in METRICS}
            for basis in ['local', 'utc']}
    manifest['seoulStations'] = {
        'file': supplement_file, 'sha256': supplement_hash,
        'startUtc': supplement['startUtc'], 'intervalMinutes': 60,
        'stationCount': 25, 'stationIds': [row['id'] for row in supplement['stations']],
        'weatherScope': 'All Seoul district PM monitors use the same Seoul ERA5 grid; no district-specific weather or individual exposure is reconstructed.',
        'temperaturePairedDaysRange': {
            basis: {'minimum': min(row[basis]['temperature']['pairedEligibleDays'] for row in district_reports.values()),
                    'maximum': max(row[basis]['temperature']['pairedEligibleDays'] for row in district_reports.values())}
            for basis in ['local', 'utc']},
    }
    print('Seoul districts: 25 original local-year starts and hourly alignment checked; same city weather grid retained.')
    return manifest, {'cities': all_reports, 'seoulDistricts': district_reports}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-manifest', action='store_true')
    parser.add_argument('--report', type=Path, help='Optional detailed coverage report, preferably outside the website.')
    args = parser.parse_args()
    generated, report = build_manifest()
    if args.update_manifest:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_bytes((json.dumps(generated, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print('Updated data/manifest.json from retained companion-project files.')
    else:
        stored, _ = read(MANIFEST)
        assert generated == stored, 'Manifest differs from source files or independent expected counts; inspect before --update-manifest.'
        print('PASS: source hashes, timestamp alignment and all stored daily-pair counts agree.')
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
