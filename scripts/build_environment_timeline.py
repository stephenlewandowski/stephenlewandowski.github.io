"""Index retained city-years and independently audit cross-project daily coverage.

No downloads. Existing 2024 manifests/files remain unchanged. New manifests
retain partial records with explicit coverage flags; advanced full-year models
require at least 75% paired-day capture in every season.
"""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from check_air_heat_data import read, daily_pairs, coverage, SEASONS, METRICS

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'projects/air-quality'
HEAT = ROOT / 'projects/heat-stress'
JOINT = ROOT / 'projects/air-heat'
CITIES = ['seoul', 'pyeongtaek', 'london', 'beijing', 'los-angeles']
YEARS = [2023, 2024, 2025]


def save(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))


def average(values):
    return sum(values) / len(values) if values else None


def pm_index(year):
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    hours = int((datetime(year + 1, 1, 1, tzinfo=timezone.utc) - start).total_seconds() / 3600)
    manifest = {'schemaVersion': 1, 'year': year, 'pollutant': 'PM2.5',
                'selectionRule': 'Audited retained observations; partial records explicitly flagged. No missing values are filled.',
                'records': [], 'excluded': []}
    summaries = []
    for city in CITIES:
        path = PM / 'data' / f'{city}-{year}.json'
        if not path.exists():
            manifest['excluded'].append({'id': city, 'reason': 'No audited same-monitor archive acquired for this year.'})
            continue
        record, digest = read(path)
        values = record['values']
        assert record['year'] == year and len(values) == hours and record['intervalMinutes'] == 60
        assert record['startUtc'] == f'{year}-01-01T00:00:00Z'
        assert all(value is None or type(value) in (float, int) and math.isfinite(value) and value >= 0 for value in values)
        valid = [v for v in values if v is not None]
        months = [(start + timedelta(hours=i)).month for i in range(hours)]
        season_values = [[v for v, month in zip(values, months) if month in includes and v is not None] for includes in SEASONS.values()]
        season_expected = [sum(month in includes for month in months) for includes in SEASONS.values()]
        capture = {name: round(100 * len(data) / expected, 3) for name, data, expected in zip(SEASONS, season_values, season_expected)}
        complete = len(valid) / hours >= .75 and all(pct >= 75 for pct in capture.values())
        listing = {'id': city, 'city': record['city'], 'file': f'data/{path.name}', 'sha256': digest,
                   'annualCapturePercent': round(100 * len(valid) / hours, 3), 'seasonCapturePercent': capture,
                   'seasonallyComplete': complete, 'included': True}
        manifest['records'].append(listing)
        summaries.append({'id': city, 'city': record['city'], 'year': year, 'validHours': len(valid),
                          'expectedHours': hours, 'mean': average(valid), 'seasonMeans': [average(v) for v in season_values],
                          'seasonCapturePercent': capture, 'seasonallyComplete': complete})
    supplement = PM / 'data' / f'seoul-stations-{year}.json'
    assert supplement.exists(), f'Seoul district archive missing: {year}'
    seoul, digest = read(supplement)
    assert seoul['year'] == year and len(seoul['stations']) == 25
    assert all(len(station['values']) == hours for station in seoul['stations'])
    manifest['seoulStations'] = {'file': f'data/{supplement.name}', 'sha256': digest}
    if year != 2024:
        save(PM / 'data' / f'manifest-{year}.json', manifest)
    return manifest, summaries


def joint_index(year, pm_manifest):
    heat_manifest_path = HEAT / 'data' / ('manifest.json' if year == 2024 else f'manifest-{year}.json')
    heat_manifest, _ = read(heat_manifest_path)
    manifest = {'schemaVersion': 1, 'year': year, 'period': {'from': f'{year}-01-01', 'through': f'{year}-12-31'},
                'metrics': heat_manifest['metrics'], 'records': [], 'pairing': {'minimumPairedHoursPerDay': 18,
                'calendar': 'UTC or fixed local standard time; complete days; both means on identical valid hours.'}}
    weather_ids = {row['id'] for row in heat_manifest['records']}
    summaries = []
    findings_path = JOINT / 'data' / ('findings.json' if year == 2024 else f'findings-{year}.json')
    findings = {city['id']: city for city in read(findings_path)[0]['cities']} if findings_path.exists() else {}
    for item in pm_manifest['records']:
        city = item['id']
        if city not in weather_ids:
            continue
        pm_file = f'../air-quality/data/{city}-{year}.json'
        heat_file = f'../heat-stress/data/{city}-{year}.json'
        pm, pm_hash = read(JOINT / pm_file)
        heat, heat_hash = read(JOINT / heat_file)
        assert len(pm['values']) == len(heat['values']['temperature'])
        assert pm['year'] == heat['year'] == year
        expected = {basis: {metric: coverage(daily_pairs(pm, heat, metric, heat['utcOffsetHours'] if basis == 'local' else 0))
                    for metric in METRICS} for basis in ['local', 'utc']}
        complete = all(c['completeDays'] and c['pairedEligibleDays'] / c['completeDays'] >= .75
                       for c in expected['local']['temperature']['seasonPairedDays'].values())
        manifest['records'].append({'id': city, 'city': pm['city'], 'utcOffsetHours': heat['utcOffsetHours'],
            'seasonallyComplete': complete,
            'pm': {'file': pm_file, 'sha256': pm_hash, 'startUtc': pm['startUtc'], 'intervalMinutes': 60,
                   'units': pm['units'], 'station': pm['station'], 'qaStatus': pm.get('quality', {}).get('qaStatus', 'See source archive quality notes.')},
            'heat': {'file': heat_file, 'sha256': heat_hash, 'startUtc': heat['startUtc'], 'intervalMinutes': 60,
                     'gridLatitude': heat['gridLatitude'], 'gridLongitude': heat['gridLongitude'], 'dataset': heat_manifest['dataset']},
            'expectedDailyPairs': expected})
        metrics = {}
        for metric in METRICS:
            rows = [row for row in daily_pairs(pm, heat, metric, heat['utcOffsetHours']) if row['eligible']]
            c = expected['local'][metric]
            metrics[metric] = {'days': len(rows), 'possibleDays': c['completeDays'],
                'seasonallyComplete': all(s['completeDays'] and s['pairedEligibleDays'] / s['completeDays'] >= .75 for s in c['seasonPairedDays'].values()),
                'meanPm': average([row['pmMean'] for row in rows]), 'meanThermal': average([row['heatMean'] for row in rows]),
                'r': c['rawPearsonR'], 'rWithin': c['withinMonthPearsonR'], 'monthlyDays': c['monthlyPairedDays']}
            if city in findings and metric in findings[city]['models']:
                model = findings[city]['models'][metric]
                metrics[metric]['adjusted'] = {'n': model['matchedN'],
                    'current': model['weatherAdjusted']['current'], 'lagSum': model['distributedLag']['cumulative']}
        summaries.append({'id': city, 'city': pm['city'], 'year': year, 'seasonallyComplete': complete, 'metrics': metrics})
    supplement = PM / 'data' / f'seoul-stations-{year}.json'
    seoul, digest = read(supplement)
    manifest['seoulStations'] = {'file': f'../air-quality/data/{supplement.name}', 'sha256': digest,
                               'startUtc': seoul['startUtc'], 'intervalMinutes': 60, 'stationCount': 25}
    if year != 2024:
        save(JOINT / 'data' / f'manifest-{year}.json', manifest)
    return summaries


def build():
    pm_rows, joint_rows = [], []
    for year in YEARS:
        manifest, rows = pm_index(year)
        pm_rows.extend(rows)
        joint_rows.extend(joint_index(year, manifest))
        print(year, len(rows), 'PM city-years indexed; partial flags retained.')
    index = {'schemaVersion': 1, 'defaultYear': 2024,
             'periods': [{'year': year, 'manifest': 'data/manifest.json' if year == 2024 else f'data/manifest-{year}.json'} for year in YEARS]}
    for project in [PM, JOINT]:
        save(project / 'data/periods.json', index)
    save(PM / 'data/timeline-summary.json', {'schemaVersion': 1, 'records': pm_rows})
    save(JOINT / 'data/timeline-summary.json', {'schemaVersion': 1, 'records': joint_rows})


if __name__ == '__main__':
    build()
