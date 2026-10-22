"""Rebuild the descriptive 2024 seasonal/weather/lag analysis.

Requires NumPy. Run with --download-weather once to archive public ERA5
precipitation, then run without network access to reproduce findings.json.
The analysis plan (spans, controls, lags and HAC bandwidths) is fixed below;
it does not select a model by statistical significance or best fit.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
try:
    import numpy as np
except ModuleNotFoundError:
    # Optional local research environment; ordinary installations need numpy.
    sys.path.insert(0, os.environ.get('AIR_HEAT_NUMPY_PATH', str(
        ROOT.parent / 'heat-stress-comparison/research/python-packages')))
    import numpy as np

from check_air_heat_data import daily_pairs, finite, parse_time, read, SEASONS

PROJECT = ROOT / 'projects/air-heat'
DATA = PROJECT / 'data'
WEATHER = DATA / 'weather-2024.json'
FINDINGS = DATA / 'findings.json'
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
SPANS = (.5, .65, .8)
METRICS = ('temperature', 'utci')


def save(path, value, compact=False):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                               separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n', encoding='utf-8')


def download_weather(manifest):
    """Store hourly ERA5 preceding-hour precipitation and response provenance."""
    year = manifest['year']
    output = {'schemaVersion': 1, 'dataset': 'ERA5 via Open-Meteo archive',
              'variable': 'precipitation', 'unit': 'mm', 'intervalMinutes': 60,
              'startUtc': f'{year}-01-01T00:00:00Z',
              'intervalMeaning': 'Sum during the preceding hour; timestamp is the interval end.',
              'extraDay': f'{year+1}-01-01 supplies the final midnight interval for local-day totals.',
              'records': []}
    for city in manifest['records']:
        h, _ = read((PROJECT / city['heat']['file']).resolve())
        query = urllib.parse.urlencode({
            'latitude': h['gridLatitude'], 'longitude': h['gridLongitude'],
            'start_date': f'{year}-01-01', 'end_date': f'{year+1}-01-01',
            'hourly': 'precipitation', 'models': 'era5', 'timezone': 'GMT',
            'elevation': 'nan', 'cell_selection': 'nearest'})
        url = 'https://archive-api.open-meteo.com/v1/archive?' + query
        with urllib.request.urlopen(url, timeout=90) as response:
            raw = response.read()
        body = json.loads(raw)
        assert body['latitude'] == h['gridLatitude']
        assert body['longitude'] == h['gridLongitude']
        times, values = body['hourly']['time'], body['hourly']['precipitation']
        start = datetime(year, 1, 1)
        expected_hours = int((datetime(year+1, 1, 2) - start).total_seconds() / 3600)
        assert len(times) == len(values) == expected_hours
        assert all(t == (start + index * HOUR).isoformat(timespec='minutes')
                   for index, t in enumerate(times))
        assert all(finite(x) and x >= 0 for x in values)
        output['records'].append({
            'id': city['id'], 'gridLatitude': body['latitude'],
            'gridLongitude': body['longitude'], 'values': values,
            'source': {'url': url, 'retrievedAt': datetime.now(timezone.utc).isoformat(),
                       'responseSha256': hashlib.sha256(raw).hexdigest(),
                       'responseMetadata': {k: v for k, v in body.items() if k != 'hourly'}}})
        print('Downloaded precipitation:', city['id'], len(values))
    save(WEATHER, output, compact=True)


def pearson(x, y):
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def smooth(x, y, grid, span):
    """Cleveland-style local linear regression with tricube distance weights.

    No robust residual iterations: concentrations, including extreme episodes,
    remain represented. The nearest ceil(span*n) points determine bandwidth.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    count = min(len(x), max(3, math.ceil(span * len(x))))
    result = []
    for at in grid:
        distance = abs(x - at)
        radius = np.partition(distance, count - 1)[count - 1]
        if radius == 0:
            result.append(float(np.mean(y[distance == 0])))
            continue
        weights = np.maximum(0, 1 - (distance / radius) ** 3) ** 3
        if not np.any(weights > 0):
            result.append(float(np.mean(y[distance == distance.min()])))
            continue
        design = np.column_stack((np.ones(len(x)), x - at))
        weighted = design * np.sqrt(weights)[:, None]
        beta, _, rank, _ = np.linalg.lstsq(weighted, y * np.sqrt(weights), rcond=None)
        result.append(float(beta[0] if rank == 2 else np.average(y, weights=weights)))
    return result


def seasonal_curves(rows):
    results = []
    for name, months in SEASONS.items():
        days = [r for r in rows if r['month'] in months]
        x = np.array([r['heatMean'] for r in days])
        y = np.array([r['pmMean'] for r in days])
        central = np.quantile(x, [.1, .9])
        grid = np.linspace(*central, 41)
        curves = {span: smooth(x, y, grid, span) for span in SPANS}
        results.append({
            'season': name, 'n': len(days), 'r': pearson(x, y),
            'xRange': [float(x.min()), float(x.max())],
            'centralRange': central.tolist(), 'meanPm': float(y.mean()),
            'curve': [{'x': float(at), 'y': curves[.65][i],
                       'span50Y': curves[.5][i], 'span80Y': curves[.8][i]}
                      for i, at in enumerate(grid)],
            'sensitivity': {f'span{int(span*100)}Delta': curves[span][-1] - curves[span][0]
                            for span in SPANS}})
    return results


def augment_days(pm, heat, rain, metric, offset_hours):
    """Use audited pairs; add matching-hour RH/wind and full-day rainfall."""
    rows = [r for r in daily_pairs(pm, heat, metric, offset_hours) if r['eligible']]
    pm_start, heat_start = parse_time(pm['startUtc']), parse_time(heat['startUtc'])
    rain_start = parse_time(rain.get('startUtc', f"{pm.get('year', 2024)}-01-01T00:00:00Z"))
    for row in rows:
        day = parse_time(row['date'] + 'T00:00:00Z')
        begin = day - timedelta(hours=offset_hours)
        heat_index = int((begin - heat_start) / HOUR)
        pm_index = int((begin - pm_start) / HOUR)
        valid = [i for i in range(24) if finite(pm['values'][pm_index + i])
                 and pm['values'][pm_index + i] >= 0
                 and finite(heat['values'][metric][heat_index + i])]
        wind = [heat['inputs']['windSpeed10m'][heat_index + i] for i in valid]
        rh = [heat['values']['humidity'][heat_index + i] for i in valid]
        rain_index = int((begin - rain_start) / HOUR)
        # A timestamp at midnight ends the previous interval; add 1..24.
        precipitation = rain['values'][rain_index + 1:rain_index + 25]
        assert len(precipitation) == 24 and all(finite(v) for v in precipitation)
        assert all(finite(v) for v in wind + rh)
        row.update(dayIndex=day.date().toordinal(), wind=float(np.mean(wind)),
                   humidity=float(np.mean(rh)), rain=float(sum(precipitation)))
    return rows


def design_fit(design, y, ordinals):
    """OLS by SVD and calendar-lag Newey-West HAC (finite-sample corrected)."""
    x, y = np.asarray(design, dtype=float), np.asarray(y, dtype=float)
    n, p = x.shape
    beta, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    if rank != p or n <= p:
        raise ValueError(f'Rank-deficient model: n={n}, p={p}, rank={rank}')
    residual = y - x @ beta
    x_plus = np.linalg.pinv(x)
    bread = x_plus @ x_plus.T
    scores = x * residual[:, None]
    calendar = {day: i for i, day in enumerate(ordinals)}
    adjacent = [(i, calendar[day - 1]) for i, day in enumerate(ordinals) if day - 1 in calendar]
    covariance = {}
    for bandwidth in (3, 7, 14):
        meat = scores.T @ scores
        for lag in range(1, bandwidth + 1):
            pairs = [(i, calendar[day - lag]) for i, day in enumerate(ordinals)
                     if day - lag in calendar]
            if pairs:
                current, previous = zip(*pairs)
                cross = scores[list(current)].T @ scores[list(previous)]
                meat += (1 - lag / (bandwidth + 1)) * (cross + cross.T)
        cov = (n / (n - p)) * bread @ meat @ bread
        covariance[bandwidth] = (cov + cov.T) / 2
    # Condition number with centered/scaled columns (excluding month dummies).
    scaled = x.copy()
    for col in range(p):
        sd = np.std(scaled[:, col])
        if sd:
            scaled[:, col] = (scaled[:, col] - np.mean(scaled[:, col])) / sd
    return {'beta': beta, 'cov': covariance, 'residual': residual,
            'sse': float(residual @ residual), 'n': n, 'p': p,
            'lag1': pearson([residual[i] for i, j in adjacent],
                            [residual[j] for i, j in adjacent]),
            'lag1Pairs': len(adjacent), 'conditionNumber': float(np.linalg.cond(scaled))}


def contrast(fit, columns):
    c = np.zeros(fit['p'])
    c[columns] = 1
    estimate = float(c @ fit['beta'])
    se = {band: math.sqrt(max(0, float(c @ cov @ c))) for band, cov in fit['cov'].items()}
    return {'estimate': estimate, 'standardError': se[7],
            'ci95': [estimate - 1.96 * se[7], estimate + 1.96 * se[7]],
            'hacSensitivity': {str(b): [estimate - 1.96 * se[b], estimate + 1.96 * se[b]]
                               for b in (3, 7, 14)}}


def fit_models(rows):
    lookup = {r['dayIndex']: r for r in rows}
    selected = [r for r in rows if all(r['dayIndex'] - lag in lookup for lag in range(4))]
    y = np.array([r['pmMean'] for r in selected])
    ordinals = [r['dayIndex'] for r in selected]
    # Intercept + eleven month indicators; all models share the same rows.
    months = np.array([[1] + [int(r['month'] == m) for m in range(2, 13)] for r in selected])
    x_lags = np.array([[lookup[r['dayIndex'] - lag]['heatMean'] for lag in range(4)] for r in selected])
    weather = np.array([[r['wind'], r['humidity'], math.log1p(r['rain'])] for r in selected])
    prior_pm = np.array([lookup[r['dayIndex'] - 1]['pmMean'] for r in selected])[:, None]
    controls = np.column_stack((months, weather))
    weather_squares = (weather[:, :2] - weather[:, :2].mean(axis=0)) ** 2
    curved_controls = np.column_stack((controls, weather_squares))
    specs = {
        'monthOnly': (np.column_stack((months, x_lags[:, :1])), months, [12]),
        'weatherAdjusted': (np.column_stack((controls, x_lags[:, :1])), controls, [15]),
        'weatherFormSensitivity': (np.column_stack((curved_controls, x_lags[:, :1])),
                                    curved_controls, [17]),
        'distributedLag': (np.column_stack((controls, x_lags)), controls, [15, 16, 17, 18]),
        'priorPmSensitivity': (np.column_stack((controls, prior_pm, x_lags)),
                               np.column_stack((controls, prior_pm)), [16, 17, 18, 19])}
    output = {'dailyN': len(rows), 'matchedN': len(selected),
              'matchedFrom': selected[0]['date'], 'matchedThrough': selected[-1]['date'],
              'monthlyMatchedDays': [sum(r['month'] == m for r in selected) for m in range(1, 13)]}
    for name, (design, base, thermal_columns) in specs.items():
        fit = design_fit(design, y, ordinals)
        reduced = design_fit(base, y, ordinals)
        # VIF computed after removing month effects, so seasonal variance is not
        # mistaken for collinearity among the meteorological/lag terms.
        month_residual_design = design[:, 12:] - months @ np.linalg.lstsq(
            months, design[:, 12:], rcond=None)[0]
        vifs = []
        for col in thermal_columns:
            at = col - 12
            target = month_residual_design[:, at]
            other = np.delete(month_residual_design, at, axis=1)
            remainder = target - other @ np.linalg.lstsq(other, target, rcond=None)[0]
            vifs.append(float((target @ target) / (remainder @ remainder)))
        record = {'n': fit['n'], 'parameterCount': fit['p'],
                  'current': contrast(fit, thermal_columns[:1]),
                  'partialR2': (reduced['sse'] - fit['sse']) / reduced['sse'],
                  'partialR2Denominator': 'Residual sum of squares of the same-row controls-only model.',
                  'residualLag1': fit['lag1'], 'residualLag1Pairs': fit['lag1Pairs'],
                  'thermalVifAfterMonth': vifs}
        if len(thermal_columns) > 1:
            record['lags'] = [contrast(fit, [col]) for col in thermal_columns]
            record['cumulative'] = contrast(fit, thermal_columns)
        output[name] = record
    return output


def build(year=2024):
    manifest, manifest_hash = read(DATA / ('manifest.json' if year == 2024 else f'manifest-{year}.json'))
    weather_path = DATA / f'weather-{year}.json'
    findings_path = DATA / ('findings.json' if year == 2024 else f'findings-{year}.json')
    weather, weather_hash = read(weather_path)
    rain_by_city = {r['id']: r for r in weather['records']}
    result = {
        'schemaVersion': 1, 'year': year, 'calendarBasis': 'local-standard',
        'methods': {
            'pairing': 'Exact UTC join; complete local-standard days with >=18 shared finite, nonnegative PM and thermal hours; both means use the same hours. No imputation; reported PM zeros retained.',
            'smoother': 'Local linear LOESS, tricube distance weights, span 0.65; 0.50 and 0.80 sensitivity. No robust residual downweighting. Display only observed x 10th–90th percentiles, 41 grid points. Descriptive curves; no confidence bands.',
            'seasons': 'Winter Jan–Feb and Dec; spring Mar–May; summer Jun–Aug; autumn Sep–Nov. Winter combines two calendar-year segments.',
            'weather': 'Current-day mean 10 m wind (m/s) and relative humidity (%) on shared PM/thermal hours; log(1+full-local-day precipitation in mm). Preceding-hour rainfall timestamps correctly cover start+1h through end. Weather controls are linear terms.',
            'models': 'All models use identical days with valid current and previous three calendar-day thermal/PM pairs. MonthOnly: month intercepts + current thermal. WeatherAdjusted adds current wind/RH/log1p(rain). DistributedLag replaces current thermal with simultaneous lags 0–3. PriorPmSensitivity adds prior-day PM to DistributedLag. WeatherFormSensitivity adds squared centered wind and RH to WeatherAdjusted, retaining log1p(rain).',
            'coefficientUnits': 'PM2.5 micrograms/m3 per 1 degree C; cumulative is the sum of simultaneous lag0–3 coefficients, corresponding to +1 degree C on each of those four days.',
            'partialR2': 'Additional thermal variance explained relative to controls-only residual sum of squares on the identical sample; one thermal term for current models, four terms for distributed-lag models. Not total model R2.',
            'hac': 'Newey–West Bartlett HAC using actual calendar-day gaps, bandwidth 7 days, n/(n−p) finite-sample correction, normal 1.96 intervals; bandwidths 3 and 14 retained as sensitivity. Not independent-day intervals.',
            'vif': 'Variance inflation for each thermal term after month removal, conditional on other included weather/lag/PM terms.',
            'limitations': [
                'Environmental concentration associations; no health outcomes, causal effects or health-interaction estimates.',
                'One year, selected PM monitors and coarse ERA5 grid weather; Seoul districts share one weather grid.',
                'UTCI assumes mean radiant temperature equals air temperature, not ERA5-HEAT; conditioning on wind/RH holds components of UTCI fixed.',
                'Lagged thermal predictors are correlated; individual lag coefficients can be unstable. The cumulative coefficient is a model contrast, not a health risk.',
                'HAC addresses coefficient uncertainty under serial dependence, not omitted-variable bias or exposure error; residual autocorrelation may remain.',
                'Pyeongtaek has only 15 eligible August days and retained reported zero concentrations; summer curves have incomplete coverage.' if year == 2024 else 'Pyeongtaek reported zeros remain retained. Check selected-year monthly coverage before interpreting seasonal curves.',
                'PM hour-start/end conventions are not uniformly documented. Reported timestamps are retained; rainfall has explicit preceding-hour intervals.',
                'Spans, controls, lags and HAC bandwidths were fixed for this descriptive follow-up; exploratory estimates are not confirmatory inference.']},
        'provenance': {'manifestSha256': manifest_hash,
                       'weatherFile': weather_path.name, 'weatherSha256': weather_hash,
                       'builder': 'scripts/build_air_heat_findings.py', 'numpyVersion': np.__version__,
                       'sourceFiles': []}, 'cities': []}
    if year != 2024:
        result['excluded'] = []
    for city in manifest['records']:
        pm_path = (PROJECT / city['pm']['file']).resolve()
        heat_path = (PROJECT / city['heat']['file']).resolve()
        pm, pm_hash = read(pm_path)
        heat, heat_hash = read(heat_path)
        assert pm_hash == city['pm']['sha256'] and heat_hash == city['heat']['sha256']
        result['provenance']['sourceFiles'].extend([
            {'file': city['pm']['file'], 'sha256': pm_hash},
            {'file': city['heat']['file'], 'sha256': heat_hash}])
        record = {'id': city['id'], 'city': city['city'], 'seasonal': {}, 'models': {}}
        eligible = city.get('seasonallyComplete', True)
        if not eligible and year != 2024:
            result['excluded'].append({'id': city['id'], 'reason': 'Below 75% paired-day coverage in at least one season; explorer remains available.'})
            continue
        for metric in METRICS:
            rows = augment_days(pm, heat, rain_by_city[city['id']], metric, city['utcOffsetHours'])
            assert len(rows) == city['expectedDailyPairs']['local'][metric]['pairedEligibleDays']
            record['seasonal'][metric] = seasonal_curves(rows)
            record['models'][metric] = fit_models(rows)
        result['cities'].append(record)
        print('Analyzed:', city['id'], 'daily', record['models']['temperature']['dailyN'],
              'lag-complete', record['models']['temperature']['matchedN'])
    save(findings_path, result, compact=True)
    print('Wrote', findings_path.relative_to(ROOT))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-weather', action='store_true')
    parser.add_argument('--year', type=int, default=2024)
    args = parser.parse_args()
    WEATHER = DATA / f'weather-{args.year}.json'
    FINDINGS = DATA / ('findings.json' if args.year == 2024 else f'findings-{args.year}.json')
    if args.download_weather:
        download_weather(read(DATA / ('manifest.json' if args.year == 2024 else f'manifest-{args.year}.json'))[0])
    build(args.year)
