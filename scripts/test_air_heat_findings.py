"""Independent numerical/pairing checks for the retained advanced findings.

Run after build_air_heat_findings.py. Uses direct double sums for the calendar
HAC reference, and residual projection (Frisch–Waugh–Lovell) for all real models.
"""
import json
import math
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
import build_air_heat_findings as analysis
from build_air_heat_findings import np


class FindingsTests(unittest.TestCase):
    def test_precipitation_interval_ends_and_shared_weather_hours(self):
        pm = {'startUtc': '2024-01-01T00:00:00Z', 'intervalMinutes': 60, 'values': [10] * 72}
        heat = {'startUtc': pm['startUtc'], 'intervalMinutes': 60, 'values': {'temperature': [20] * 72,
                'humidity': [60] * 72}, 'inputs': {'windSpeed10m': [2] * 72}}
        # Jan 2 local UTC+9 starts at index 15. Its rain interval ends are 16..39.
        pm['values'][15] = None
        heat['inputs']['windSpeed10m'][15] = 100
        heat['values']['humidity'][15] = 10
        rain = {'values': [0] * 100}
        for index, value in [(15, 100), (16, 1), (39, 2), (40, 10)]:
            rain['values'][index] = value
        rows = analysis.augment_days(pm, heat, rain, 'temperature', 9)
        self.assertEqual([row['date'] for row in rows], ['2024-01-02', '2024-01-03'])
        self.assertEqual([row['rain'] for row in rows], [3, 10])
        self.assertEqual(rows[0]['pairedHours'], 23)
        self.assertEqual(rows[0]['wind'], 2)
        self.assertEqual(rows[0]['humidity'], 60)

    def test_loess_preserves_line_including_tails(self):
        x = np.linspace(-10, 30, 77)
        grid = np.linspace(-8, 27, 31)
        for span in analysis.SPANS:
            actual = analysis.smooth(x, 7 + 2.25 * x, grid, span)
            np.testing.assert_allclose(actual, 7 + 2.25 * grid, atol=1e-10)
        self.assertEqual(analysis.smooth([1, 1, 1], [2, 3, 4], [1], .65), [3])
        self.assertEqual(analysis.smooth([-1, -1, 1, 1], [2, 2, 4, 4], [0], .65), [3])

    def test_calendar_hac_against_double_sum(self):
        rng = np.random.default_rng(82024)
        calendar = np.array([1, 2, 3, 6, 7, 10, 11, 12, 14, 15, 16, 18, 20, 21, 24])
        x = np.column_stack((np.ones(len(calendar)), rng.normal(size=(len(calendar), 2))))
        y = 2 + x[:, 1] - .3 * x[:, 2] + rng.normal(size=len(calendar))
        actual = analysis.design_fit(x, y, calendar)
        beta = np.linalg.solve(x.T @ x, x.T @ y)
        residual = y - x @ beta
        bread = np.linalg.inv(x.T @ x)
        for band in (3, 7, 14):
            meat = np.zeros((3, 3))
            for i, day_i in enumerate(calendar):
                for j, day_j in enumerate(calendar):
                    lag = abs(day_i - day_j)
                    if lag <= band:
                        weight = 1 - lag / (band + 1)
                        meat += weight * residual[i] * residual[j] * np.outer(x[i], x[j])
            reference = len(y) / (len(y) - 3) * bread @ meat @ bread
            np.testing.assert_allclose(actual['cov'][band], reference, atol=1e-11)
        summed = analysis.contrast(actual, [1, 2])
        self.assertAlmostEqual(summed['estimate'], beta[1] + beta[2])
        self.assertAlmostEqual(summed['standardError'] ** 2,
                               sum(actual['cov'][7][i, j] for i in (1, 2) for j in (1, 2)))

    def test_sources_and_real_model_fwl(self):
        manifest, manifest_hash = analysis.read(analysis.DATA / 'manifest.json')
        findings, _ = analysis.read(analysis.FINDINGS)
        weather, weather_hash = analysis.read(analysis.WEATHER)
        self.assertEqual(findings['provenance']['manifestSha256'], manifest_hash)
        self.assertEqual(findings['provenance']['weatherSha256'], weather_hash)
        rain_by_city = {r['id']: r for r in weather['records']}
        out_by_city = {r['id']: r for r in findings['cities']}
        for city in manifest['records']:
            pm, _ = analysis.read((analysis.PROJECT / city['pm']['file']).resolve())
            heat, _ = analysis.read((analysis.PROJECT / city['heat']['file']).resolve())
            rain = rain_by_city[city['id']]
            self.assertEqual(len(rain['values']), 8808)
            self.assertTrue(all(v >= 0 for v in rain['values']))
            for metric in analysis.METRICS:
                rows = analysis.augment_days(pm, heat, rain, metric, city['utcOffsetHours'])
                lookup = {r['dayIndex']: r for r in rows}
                selected = [r for r in rows if all(r['dayIndex'] - i in lookup for i in range(4))]
                out = out_by_city[city['id']]['models'][metric]
                self.assertEqual(out['dailyN'], len(rows))
                self.assertEqual(out['matchedN'], len(selected))
                months = np.array([[int(r['month'] == m) for m in range(1, 13)] for r in selected])
                weather_x = np.array([[r['wind'], r['humidity'], math.log1p(r['rain'])] for r in selected])
                weather_squares = (weather_x[:, :2] - weather_x[:, :2].mean(axis=0)) ** 2
                prior = np.array([lookup[r['dayIndex'] - 1]['pmMean'] for r in selected])[:, None]
                lag_x = np.array([[lookup[r['dayIndex'] - i]['heatMean'] for i in range(4)] for r in selected])
                y = np.array([r['pmMean'] for r in selected])
                for name, controls, thermal in (
                    ('monthOnly', months, lag_x[:, :1]),
                    ('weatherAdjusted', np.column_stack((months, weather_x)), lag_x[:, :1]),
                    ('weatherFormSensitivity', np.column_stack((months, weather_x, weather_squares)), lag_x[:, :1]),
                    ('distributedLag', np.column_stack((months, weather_x)), lag_x),
                    ('priorPmSensitivity', np.column_stack((months, weather_x, prior)), lag_x)):
                    # Independent residualized design, then a small solve.
                    residual_y = y - controls @ np.linalg.lstsq(controls, y, rcond=None)[0]
                    residual_x = thermal - controls @ np.linalg.lstsq(controls, thermal, rcond=None)[0]
                    beta = np.linalg.solve(residual_x.T @ residual_x, residual_x.T @ residual_y)
                    fitted = residual_x @ beta
                    residual = residual_y - fitted
                    partial_r2 = 1 - float(residual @ residual) / float(residual_y @ residual_y)
                    self.assertAlmostEqual(out[name]['current']['estimate'], beta[0], places=9)
                    self.assertAlmostEqual(out[name]['partialR2'], partial_r2, places=10)
                    if len(beta) > 1:
                        self.assertAlmostEqual(out[name]['cumulative']['estimate'], sum(beta), places=9)
                    self.assertEqual(out[name]['n'], len(selected))
                seasons = out_by_city[city['id']]['seasonal'][metric]
                self.assertEqual(sum(s['n'] for s in seasons), len(rows))
                for season in seasons:
                    self.assertEqual(len(season['curve']), 41)
                    self.assertGreaterEqual(season['centralRange'][0], season['xRange'][0])
                    self.assertLessEqual(season['centralRange'][1], season['xRange'][1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
