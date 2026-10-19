"""Check retained measured PM2.5 data, source hashes and seasonal eligibility."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'projects' / 'air-quality'
manifest = json.loads((PROJECT / 'data' / 'manifest.json').read_text(encoding='utf-8'))
seasons = {'Winter (Jan–Feb, Dec)': (1, 2, 12), 'Spring (Mar–May)': (3, 4, 5),
           'Summer (Jun–Aug)': (6, 7, 8), 'Autumn (Sep–Nov)': (9, 10, 11)}
start = datetime(2024, 1, 1, tzinfo=timezone.utc)
months = [(start + timedelta(hours=hour)).month for hour in range(8784)]
assert manifest['records'][0]['id'] == 'seoul'
assert len({item['id'] for item in manifest['records']}) == len(manifest['records'])
for item in manifest['records']:
    path = PROJECT / item['file']
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item['sha256'], f'Hash mismatch: {path}'
    record = json.loads(raw)
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
print('PASS retained 2024 PM2.5 data.')
