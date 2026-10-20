"""Check retained measured PM2.5 data, source hashes and seasonal eligibility."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'projects' / 'air-quality'


def check_seoul_stations(supplement, utc_network):
    """Check packaged local-year district data without any raw source caches."""
    assert supplement['schemaVersion'] == 1 and supplement['city'] == 'Seoul'
    assert supplement['year'] == 2024 and supplement['pollutant'] == 'PM2.5'
    assert supplement['units'] == 'µg/m³' and supplement['timeZone'] == 'Asia/Seoul'
    assert supplement['startUtc'] == '2023-12-31T15:00:00Z'
    assert supplement['intervalMinutes'] == 60
    assert supplement['timeConvention'] == utc_network['timeConvention']
    source_hash = supplement['sourceSha256']
    assert len(source_hash) == 64 and all(character in '0123456789abcdef' for character in source_hash)
    assert source_hash == utc_network['sources'][0]['sha256']
    assert supplement['sources'] and supplement['sources'][0]['sha256'] == source_hash
    for field in ('url', 'pageUrl', 'attribution', 'license', 'bytes'):
        assert supplement['sources'][0][field] == utc_network['sources'][0][field], field

    stations = supplement['stations']
    assert len(stations) == 25
    station_ids = [station['id'] for station in stations]
    source_ids = [station['sourceStationId'] for station in stations]
    assert len(set(station_ids)) == len(set(source_ids)) == 25
    assert source_ids == utc_network['station']['stationIds']
    assert all(station['id'] == f"seoul-{station['sourceStationId']}" for station in stations)
    assert all(station['name'] and station['sourceName'] for station in stations)
    local_start = datetime(2024, 1, 1)
    local_months = [(local_start + timedelta(hours=hour)).month for hour in range(8784)]
    season_months = ((1, 2, 12), (3, 4, 5), (6, 7, 8), (9, 10, 11))
    network = supplement['network']
    assert network['id'] == utc_network['station']['id']
    assert network['stationIds'] == station_ids
    assert network['minimumStationsPerHour'] == utc_network['station']['minimumStationsPerHour'] == 20
    for series in [network, *stations]:
        label = series['id']
        values = series['values']
        assert len(values) == 8784, f'{label}: wrong local-year length'
        assert all(value is None or type(value) in (int, float)
                   and math.isfinite(value) and value >= 0 for value in values), f'{label}: invalid value'
        valid = sum(value is not None for value in values)
        assert series['validHours'] == valid, f'{label}: incorrect valid-hour count'
        capture = round(valid / 8784 * 100, 3)
        assert series['capturePercent'] == capture and capture >= 75, f'{label}: incorrect annual capture'
        for included in season_months:
            selected = [value for value, month in zip(values, local_months) if month in included]
            assert sum(value is not None for value in selected) / len(selected) >= 0.75, \
                f'{label}: a local-calendar season has less than 75% capture'

    counts = network['stationCounts']
    assert len(counts) == 8784
    assert all(type(count) is int and 0 <= count <= 25 for count in counts)
    for hour, (value, count) in enumerate(zip(network['values'], counts)):
        observed = [station['values'][hour] for station in stations if station['values'][hour] is not None]
        assert count == len(observed), f'Hour {hour}: network count differs from district values'
        assert (value is not None) == (count >= 20), f'Hour {hour}: network minimum-count rule differs'
        expected = round(sum(observed) / count, 2) if count >= 20 else None
        assert value == expected, f'Hour {hour}: network mean differs from district values'
    # KST local-year labels include nine UTC-2023 hours and end nine hours before
    # UTC year-end. The existing UTC series leaves those unavailable final hours null.
    assert network['values'][9:] + [None] * 9 == utc_network['values']
    assert counts[9:] + [0] * 9 == utc_network['stationCounts']
    print('PASS Seoul districts: 25 local-year series; counts, means, capture, provenance and UTC alignment checked.')


manifest = json.loads((PROJECT / 'data' / 'manifest.json').read_text(encoding='utf-8'))
seasons = {'Winter (Jan–Feb, Dec)': (1, 2, 12), 'Spring (Mar–May)': (3, 4, 5),
           'Summer (Jun–Aug)': (6, 7, 8), 'Autumn (Sep–Nov)': (9, 10, 11)}
start = datetime(2024, 1, 1, tzinfo=timezone.utc)
months = [(start + timedelta(hours=hour)).month for hour in range(8784)]
assert manifest['records'][0]['id'] == 'seoul'
assert len({item['id'] for item in manifest['records']}) == len(manifest['records'])
records = {}
for item in manifest['records']:
    path = PROJECT / item['file']
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item['sha256'], f'Hash mismatch: {path}'
    record = json.loads(raw)
    records[item['id']] = record
    assert record['id'] == item['id'] and record['year'] == 2024
    assert record['startUtc'] == '2024-01-01T00:00:00Z' and record['intervalMinutes'] == 60
    values = record['values']
    assert len(values) == 8784
    assert all(value is None or isinstance(value, (float, int)) and math.isfinite(value) and value >= 0 for value in values)
    valid = sum(value is not None for value in values)
    assert valid == record['quality']['validHours']
    assert abs(round(valid / 8784 * 100, 3) - item['annualCapturePercent']) < 1e-9
    for name, included in seasons.items():
        hours = [value for value, month in zip(values, months) if month in included]
        percent = round(sum(value is not None for value in hours) / len(hours) * 100, 3)
        assert percent >= 75 and abs(percent - item['seasonCapturePercent'][name]) < 1e-9
    for month in record['monthlyCapture']:
        selected = [value for value, number in zip(values, months) if number == month['month']]
        assert month['expectedHours'] == len(selected)
        assert month['validHours'] == sum(value is not None for value in selected)
    assert record['sources'] and all(source.get('url') and len(source.get('sha256', '')) == 64 for source in record['sources'])
    if item['id'] == 'seoul':
        assert len(record['stationCounts']) == 8784
        assert all((value is not None) == (count >= 20) for value, count in zip(values, record['stationCounts']))
    print(f"PASS {record['city']}: {valid:,}/8,784 hours; every season >=75%; provenance and grid checked.")
supplement = json.loads((PROJECT / 'data' / 'seoul-stations-2024.json').read_text(encoding='utf-8'))
check_seoul_stations(supplement, records['seoul'])
print('PASS retained 2024 PM2.5 data.')
