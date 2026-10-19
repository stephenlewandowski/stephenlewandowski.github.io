"""Package audited 2024 station series for the static comparison page.

The source directory contains data/seoul/seoul-2024.json and
data/comparisons/{city}-2024.json, produced by the public acquisition scripts.
Only records with >=75% capture in the year and every meteorological season pass.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'projects' / 'air-quality' / 'data'
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
SEASONS = {'Winter (Jan–Feb, Dec)': (1, 2, 12), 'Spring (Mar–May)': (3, 4, 5),
           'Summer (Jun–Aug)': (6, 7, 8), 'Autumn (Sep–Nov)': (9, 10, 11)}


def capture(values):
    return sum(value is not None for value in values) / len(values) * 100


def audit(record):
    values = record['values']
    assert len(values) == 8784 and record['year'] == 2024 and record['intervalMinutes'] == 60
    assert all(value is None or isinstance(value, (float, int)) and value >= 0 for value in values)
    months = [(START + timedelta(hours=hour)).month for hour in range(8784)]
    seasons = {name: round(capture([value for value, month in zip(values, months) if month in included]), 3)
               for name, included in SEASONS.items()}
    annual = round(capture(values), 3)
    return {'annualCapturePercent': annual, 'seasonCapturePercent': seasons,
            'included': annual >= 75 and all(percent >= 75 for percent in seasons.values())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT.parent / 'air-quality-comparison')
    args = parser.parse_args()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = {'schemaVersion': 1, 'year': 2024, 'pollutant': 'PM2.5',
                'selectionRule': 'At least 75% of UTC hours in 2024 and in each meteorological season; Seoul required.',
                'records': [], 'excluded': []}
    for city in ['seoul', 'london', 'beijing', 'delhi']:
        folder = 'seoul' if city == 'seoul' else 'comparisons'
        source = args.source_root / 'data' / folder / f'{city}-2024.json'
        if not source.exists():
            manifest['excluded'].append({'id': city, 'reason': 'A complete audited annual series was not prepared for this version.'})
            continue
        record = json.loads(source.read_text(encoding='utf-8'))
        eligibility = audit(record)
        if not eligibility['included']:
            manifest['excluded'].append({'id': city, 'reason': 'Insufficient capture in at least one season.', **eligibility})
            continue
        name = f'{city}-2024.json'
        raw = source.read_bytes()
        (DESTINATION / name).write_bytes(raw)
        manifest['records'].append({'id': city, 'city': record['city'], 'file': f'data/{name}',
                                    'sha256': hashlib.sha256(raw).hexdigest(), **eligibility})
    assert any(record['id'] == 'seoul' for record in manifest['records']), 'Seoul must be present.'
    (DESTINATION / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    research = ROOT / 'projects' / 'air-quality' / 'research'
    research.mkdir(exist_ok=True)
    for name in ['acquire_seoul_2024.py', 'acquire_comparisons_2024.py']:
        source_script = args.source_root / 'research' / name
        if source_script.resolve() != (research / name).resolve():
            shutil.copyfile(source_script, research / name)
    print(json.dumps(manifest, ensure_ascii=True, indent=2))
