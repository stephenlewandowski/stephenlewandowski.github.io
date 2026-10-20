"""Fetch the public hourly ERA5 inputs for the 2024 city heat comparison.

The default destination is outside the website repository. Existing raw files
are checked and reused unless --refresh is specified. No API key is required.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    'temperature_2m', 'relative_humidity_2m', 'dew_point_2m', 'wind_speed_10m',
    'surface_pressure', 'shortwave_radiation', 'direct_radiation', 'diffuse_radiation',
    'direct_normal_irradiance', 'shortwave_radiation_instant', 'direct_radiation_instant',
    'diffuse_radiation_instant', 'direct_normal_irradiance_instant',
]
CITIES = [
    ('seoul', 'Seoul', 37.5665, 126.978, 'Asia/Seoul'),
    ('pyeongtaek', 'Pyeongtaek', 37.0159, 127.1172, 'Asia/Seoul'),
    ('london', 'London', 51.5074, -0.1278, 'Europe/London'),
    ('beijing', 'Beijing', 39.9042, 116.4074, 'Asia/Shanghai'),
    ('los-angeles', 'Los Angeles', 34.0522, -118.2437, 'America/Los_Angeles'),
]
START = datetime(2024, 1, 1)
EXPECTED_TIMES = [(START + timedelta(hours=hour)).isoformat(timespec='minutes') for hour in range(8784)]


def source_url(latitude, longitude):
    """Pin one model and its native nearest grid cell, without elevation adjustment."""
    query = {
        'latitude': latitude, 'longitude': longitude,
        'start_date': '2024-01-01', 'end_date': '2024-12-31',
        'hourly': ','.join(FIELDS), 'models': 'era5', 'wind_speed_unit': 'ms',
        'timezone': 'GMT', 'elevation': 'nan', 'cell_selection': 'nearest',
    }
    return 'https://archive-api.open-meteo.com/v1/archive?' + urllib.parse.urlencode(query, safe=',')


def audit(data):
    """Reject incomplete time grids and unusable meteorological inputs."""
    assert data['utc_offset_seconds'] == 0
    assert data['hourly']['time'] == EXPECTED_TIMES, 'Expected the complete 8,784-hour UTC year.'
    for field in FIELDS:
        values = data['hourly'][field]
        assert len(values) == len(EXPECTED_TIMES), field
        assert all(type(value) in (int, float) and math.isfinite(value) for value in values), field
    assert all(0 <= value <= 100 for value in data['hourly']['relative_humidity_2m'])
    assert all(value >= 0 for value in data['hourly']['wind_speed_10m'])
    assert all(value > 0 for value in data['hourly']['surface_pressure'])
    for field in FIELDS[5:]:
        assert all(value >= 0 for value in data['hourly'][field]), field
    assert data['hourly_units']['temperature_2m'] == '\u00b0C'
    assert data['hourly_units']['relative_humidity_2m'] == '%'
    assert data['hourly_units']['wind_speed_10m'] == 'm/s'
    assert data['hourly_units']['surface_pressure'] == 'hPa'


def input_hash(data):
    """Hash retained inputs, excluding the API's variable generation-time field."""
    retained = {key: data[key] for key in [
        'latitude', 'longitude', 'elevation', 'utc_offset_seconds', 'hourly_units', 'hourly'
    ]}
    raw = json.dumps(retained, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def acquire(city, raw_root, previous, refresh=False):
    slug, name, latitude, longitude, civil_tz = city
    url = source_url(latitude, longitude)
    path = raw_root / f'{slug}-era5-2024.json'
    old = previous.get(slug, {})
    if path.exists() and not refresh:
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if old.get('sha256'):
            assert digest == old['sha256'], f'{slug}: cached raw file differs from provenance.'
        retrieved_at = old.get('retrievedAt')
    else:
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'CityHeatComparisonResearch/1.0'})
                with urllib.request.urlopen(request, timeout=180) as response:
                    content = response.read()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
        retrieved_at = datetime.now(timezone.utc).isoformat()
        path.write_bytes(content)
    data = json.loads(content)
    audit(data)
    result = {
        'id': slug, 'city': name, 'requestedLatitude': latitude,
        'requestedLongitude': longitude, 'civilTimezone': civil_tz,
        'returnedGridLatitude': data['latitude'], 'returnedGridLongitude': data['longitude'],
        'gridElevationMetres': data['elevation'], 'timeBasis': 'UTC', 'hours': 8784,
        'file': path.name, 'bytes': len(content),
        'sha256': hashlib.sha256(content).hexdigest(), 'inputSha256': input_hash(data),
        'url': url, 'retrievedAt': retrieved_at, 'units': data['hourly_units'],
    }
    print(f"{name}: 8,784 complete hours; grid {data['latitude']}, {data['longitude']}")
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=ROOT.parent / 'heat-stress-comparison' / 'research')
    parser.add_argument('--refresh', action='store_true', help='Download again instead of reusing audited raw files.')
    args = parser.parse_args()
    raw_root = args.output_root / 'raw'
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_root / 'open-meteo-provenance.json'
    previous = {}
    if manifest_path.exists():
        previous = {record['id']: record for record in json.loads(manifest_path.read_text(encoding='utf-8'))['sources']}
    sources = [acquire(city, raw_root, previous, args.refresh) for city in CITIES]
    provenance = {
        'dataset': 'ERA5 reanalysis, accessed via Open-Meteo Historical Weather API',
        'documentation': 'https://open-meteo.com/en/docs/historical-weather-api',
        'licence': 'https://open-meteo.com/en/licence',
        'period': '2024-01-01T00:00Z/2024-12-31T23:00Z',
        'nativeGrid': True,
        'selection': 'models=era5, elevation=nan disables elevation adjustment; cell_selection=nearest',
        'radiation': 'Hourly average radiation is over the preceding hour; *_instant fields are Open-Meteo instantaneous-time estimates.',
        'hashes': 'sha256 records exact API response bytes; inputSha256 excludes generationtime_ms and uses sorted compact JSON.',
        'sources': sources,
    }
    manifest_path.write_bytes((json.dumps(provenance, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
