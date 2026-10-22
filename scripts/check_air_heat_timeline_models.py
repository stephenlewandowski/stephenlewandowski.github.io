"""Independently verify the additional-year weather and lag models.

Read-only, with no network calls. Uses the standard-library daily-pair audit,
then reconstructs weather controls from retained hourly records. Thermal OLS
coefficients use Frisch-Waugh-Lovell residual projection. HAC covariance uses
a dense calendar-distance Bartlett kernel and the SVD pseudoinverse of the
projected thermal predictors, rather than the builder's lag-accumulation loop.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlparse

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
try:
    import numpy as np
except ModuleNotFoundError:
    sys.path.insert(0, os.environ.get('AIR_HEAT_NUMPY_PATH', str(
        ROOT.parent / 'heat-stress-comparison/research/python-packages')))
    import numpy as np

from check_air_heat_data import daily_pairs

PROJECT = ROOT / 'projects/air-heat'
DATA = PROJECT / 'data'
HOUR = timedelta(hours=1)
METRICS = ('temperature', 'utci')
SPECS = ('monthOnly', 'weatherAdjusted', 'weatherFormSensitivity',
         'distributedLag', 'priorPmSensitivity')
SEASONS = ((1, 2, 12), (3, 4, 5), (6, 7, 8), (9, 10, 11))


def read(path):
    raw = path.read_bytes().replace(b'\r\n', b'\n')
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def close(actual, expected, label, errors, tolerance):
    assert np.all(np.isfinite(actual)) and np.all(np.isfinite(expected)), label
    error = float(np.max(np.abs(np.asarray(actual) - np.asarray(expected))))
    errors[label.split(':')[0]] = max(errors.get(label.split(':')[0], 0), error)
    assert error <= tolerance, f'{label}: absolute difference {error:g} exceeds {tolerance:g}'


def verify_rain(weather, city, heat, year):
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    hours = int((datetime(year + 1, 1, 1, tzinfo=timezone.utc) - start) / HOUR)
    assert weather['startUtc'] == f'{year}-01-01T00:00:00Z'
    assert weather['intervalMinutes'] == 60 and weather['unit'] == 'mm'
    assert weather['variable'] == 'precipitation'
    assert 'preceding hour' in weather['intervalMeaning']
    values = city['values']
    assert len(values) == hours + 24, f'{city["id"]}: missing extra precipitation day'
    assert all(finite(value) and value >= 0 for value in values)
    assert city['gridLatitude'] == heat['gridLatitude']
    assert city['gridLongitude'] == heat['gridLongitude']
    source = city['source']
    parsed = urlparse(source['url'])
    assert parsed.scheme == 'https' and parsed.netloc == 'archive-api.open-meteo.com'
    query = parse_qs(parsed.query)
    for key, expected in {'start_date': f'{year}-01-01', 'end_date': f'{year+1}-01-01',
                          'hourly': 'precipitation', 'models': 'era5', 'timezone': 'GMT',
                          'elevation': 'nan', 'cell_selection': 'nearest'}.items():
        assert query[key] == [expected], f'{city["id"]}: incorrect rainfall request {key}'
    assert float(query['latitude'][0]) == heat['gridLatitude']
    assert float(query['longitude'][0]) == heat['gridLongitude']
    assert re.fullmatch(r'[a-f0-9]{64}', source['responseSha256'])
    metadata = source['responseMetadata']
    assert metadata['utc_offset_seconds'] == 0
    assert metadata['hourly_units']['precipitation'] == 'mm'
    # The API response bytes are not redistributed, so their recorded hash
    # cannot be recomputed here. The retained weather archive's hash IS checked.
    return {start + hour * HOUR: value for hour, value in enumerate(values)}


def reconstruct(pm, heat, rain_by_end, metric, offset):
    rows = daily_pairs(pm, heat, metric, offset)
    start_pm, start_heat = timestamp(pm['startUtc']), timestamp(heat['startUtc'])
    selected = []
    for day in rows:
        if not day['eligible']:
            continue
        local_date = datetime.strptime(day['date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
        begin = local_date - timedelta(hours=offset)
        matched = []
        for hour in range(24):
            instant = begin + hour * HOUR
            p_index = int((instant - start_pm) / HOUR)
            h_index = int((instant - start_heat) / HOUR)
            pollution, thermal = pm['values'][p_index], heat['values'][metric][h_index]
            if finite(pollution) and pollution >= 0 and finite(thermal):
                matched.append(h_index)
        assert len(matched) == day['pairedHours'] >= 18
        wind = [heat['inputs']['windSpeed10m'][i] for i in matched]
        humidity = [heat['values']['humidity'][i] for i in matched]
        assert all(finite(v) for v in wind + humidity)
        # Rain labels END intervals. Start+1 ... start+24 exactly covers the
        # local day's 24 hourly intervals, including its final midnight end.
        ends = [begin + HOUR * hour for hour in range(1, 25)]
        rain = [rain_by_end[end] for end in ends]
        assert ends[0] - HOUR == begin and ends[-1] == begin + 24 * HOUR
        selected.append({**day, 'ordinal': local_date.date().toordinal(),
                         'wind': sum(wind) / len(wind),
                         'humidity': sum(humidity) / len(humidity), 'rain': sum(rain)})
    return rows, selected


def projected_fit(controls, thermal, y, ordinals):
    """FWL point estimates and direct calendar-kernel covariance."""
    c_plus = np.linalg.pinv(controls)
    z = thermal - controls @ (c_plus @ thermal)
    target = y - controls @ (c_plus @ y)
    u, singular, vt = np.linalg.svd(z, full_matrices=False)
    assert singular[-1] > singular[0] * 1e-12, 'Thermal residual design is deficient'
    z_plus = (vt.T / singular) @ u.T
    gamma = z_plus @ target
    remainder = y - thermal @ gamma
    residual = remainder - controls @ (c_plus @ remainder)
    n, p = len(y), controls.shape[1] + thermal.shape[1]
    assert np.linalg.matrix_rank(np.column_stack((controls, thermal))) == p and n > p
    distances = np.abs(ordinals[:, None] - ordinals[None, :])
    influence = z_plus * residual[None, :]
    covariance = {}
    for bandwidth in (3, 7, 14):
        kernel = np.maximum(0, 1 - distances / (bandwidth + 1))
        covariance[bandwidth] = n / (n - p) * influence @ kernel @ influence.T
    reduced_residual = y - controls @ (c_plus @ y)
    partial_r2 = 1 - (residual @ residual) / (reduced_residual @ reduced_residual)
    return gamma, covariance, residual, partial_r2, p


def verify_models(rows, stored, label, errors, tolerance):
    lookup = {row['ordinal']: row for row in rows}
    selected = [row for row in rows if all(row['ordinal'] - lag in lookup for lag in range(4))]
    assert stored['dailyN'] == len(rows) and stored['matchedN'] == len(selected)
    assert stored['matchedFrom'] == selected[0]['date'] and stored['matchedThrough'] == selected[-1]['date']
    assert stored['monthlyMatchedDays'] == [sum(row['month'] == m for row in selected) for m in range(1, 13)]
    y = np.array([row['pmMean'] for row in selected])
    ordinals = np.array([row['ordinal'] for row in selected])
    months = np.column_stack((np.ones(len(selected)),
                             *[np.array([row['month'] == m for row in selected], dtype=float)
                               for m in range(2, 13)]))
    weather = np.array([[row['wind'], row['humidity'], math.log1p(row['rain'])] for row in selected])
    controls = np.column_stack((months, weather))
    curved = np.column_stack((controls, (weather[:, :2] - weather[:, :2].mean(axis=0)) ** 2))
    thermal = np.array([[lookup[row['ordinal'] - lag]['heatMean'] for lag in range(4)] for row in selected])
    prior_pm = np.array([lookup[row['ordinal'] - 1]['pmMean'] for row in selected])[:, None]
    specs = {'monthOnly': (months, thermal[:, :1]),
             'weatherAdjusted': (controls, thermal[:, :1]),
             'weatherFormSensitivity': (curved, thermal[:, :1]),
             'distributedLag': (controls, thermal),
             'priorPmSensitivity': (np.column_stack((controls, prior_pm)), thermal)}
    checked = 0
    for name in SPECS:
        base, predictors = specs[name]
        gamma, covariance, residual, partial_r2, p = projected_fit(base, predictors, y, ordinals)
        record = stored[name]
        assert record['n'] == len(y) and record['parameterCount'] == p
        close(partial_r2, record['partialR2'], f'partialR2:{label}/{name}', errors, tolerance)
        pairs = [(i, i-1) for i in range(1, len(ordinals)) if ordinals[i] - ordinals[i-1] == 1]
        assert record['residualLag1Pairs'] == len(pairs)
        if len(pairs) > 2:
            actual = np.corrcoef([residual[i] for i, j in pairs], [residual[j] for i, j in pairs])[0, 1]
            close(actual, record['residualLag1'], f'residualLag1:{label}/{name}', errors, tolerance)
        contrasts = [('current', np.eye(len(gamma))[0], record['current'])]
        if len(gamma) > 1:
            contrasts += [(f'lag{i}', np.eye(len(gamma))[i], row) for i, row in enumerate(record['lags'])]
            contrasts.append(('lagSum', np.ones(len(gamma)), record['cumulative']))
        for contrast_name, weights, published in contrasts:
            estimate = float(weights @ gamma)
            close(estimate, published['estimate'], f'coefficient:{label}/{name}/{contrast_name}', errors, tolerance)
            for bandwidth in (3, 7, 14):
                se = math.sqrt(max(0, float(weights @ covariance[bandwidth] @ weights)))
                interval = [estimate - 1.96 * se, estimate + 1.96 * se]
                close(interval, published['hacSensitivity'][str(bandwidth)], f'ci:{label}/{name}/{contrast_name}/hac{bandwidth}', errors, tolerance)
                if bandwidth == 7:
                    close(se, published['standardError'], f'standardError:{label}/{name}/{contrast_name}', errors, tolerance)
                    close(interval, published['ci95'], f'ci95:{label}/{name}/{contrast_name}', errors, tolerance)
        checked += 1
    return checked


def verify_year(year, errors, tolerance):
    manifest, manifest_hash = read(DATA / f'manifest-{year}.json')
    findings, _ = read(DATA / f'findings-{year}.json')
    weather_path = DATA / f'weather-{year}.json'
    weather, weather_hash = read(weather_path)
    assert manifest['year'] == findings['year'] == year
    assert findings['calendarBasis'] == 'local-standard'
    provenance = findings['provenance']
    assert provenance['manifestSha256'] == manifest_hash
    assert provenance['weatherFile'] == weather_path.name and provenance['weatherSha256'] == weather_hash
    sources = {item['file']: item['sha256'] for item in provenance['sourceFiles']}
    rain = {row['id']: row for row in weather['records']}
    modeled = {row['id']: row for row in findings['cities']}
    excluded = {row['id'] for row in findings.get('excluded', [])}
    expected = {row['id'] for row in manifest['records']}
    assert set(modeled).isdisjoint(excluded) and set(modeled) | excluded == expected
    assert set(rain) == expected
    count = 0
    for city in manifest['records']:
        pm, pm_hash = read((PROJECT / city['pm']['file']).resolve())
        heat, heat_hash = read((PROJECT / city['heat']['file']).resolve())
        assert pm_hash == city['pm']['sha256'] == sources[city['pm']['file']]
        assert heat_hash == city['heat']['sha256'] == sources[city['heat']['file']]
        assert pm['year'] == heat['year'] == year
        assert pm['startUtc'] == heat['startUtc'] == f'{year}-01-01T00:00:00Z'
        rain_by_end = verify_rain(weather, rain[city['id']], heat, year)
        for metric in METRICS:
            all_days, rows = reconstruct(pm, heat, rain_by_end, metric, city['utcOffsetHours'])
            assert len(rows) == city['expectedDailyPairs']['local'][metric]['pairedEligibleDays']
            complete = all(sum(row['eligible'] for row in all_days if row['month'] in months)
                           / sum(row['month'] in months for row in all_days) >= .75
                           for months in SEASONS)
            assert complete == city['seasonallyComplete']
            if city['id'] in excluded:
                assert not complete
                continue
            assert complete
            count += verify_models(rows, modeled[city['id']]['models'][metric],
                                   f'{year}/{city["id"]}/{metric}', errors, tolerance)
    print(f'PASS {year}: {len(modeled)} modeled cities, {len(excluded)} excluded partial record(s), '
          f'{count} independent OLS/HAC specifications; source hashes and rainfall windows verified.')
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--years', nargs='+', type=int, default=[2023, 2025])
    parser.add_argument('--tolerance', type=float, default=1e-8)
    args = parser.parse_args()
    errors = {}
    total = sum(verify_year(year, errors, args.tolerance) for year in args.years)
    print(f'PASS {total} additional-year model specifications. Maximum absolute differences: '
          + ', '.join(f'{key}={value:.3g}' for key, value in sorted(errors.items())) + '.')
