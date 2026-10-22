import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {yearGrid, monthlySummary} from '../projects/air-quality/analysis.mjs';
import {pm25Benchmark, thresholdCounts} from '../projects/air-quality/benchmarks.mjs';
import {dailyPairs} from '../projects/air-heat/analysis.mjs';
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));

test('leap and non-leap grids use the actual calendar year and month boundaries', () => {
  for (const year of [2023, 2024, 2025]) {
    const {hours, start} = yearGrid(year);
    assert.equal(hours, year === 2024 ? 8784 : 8760);
    assert.equal(new Date(start).getUTCFullYear(), year);
    const monthly = monthlySummary(Array(hours).fill(10), year);
    assert.equal(monthly[1].count, (year === 2024 ? 29 : 28) * 24);
    assert.equal(monthly[2].count, 31 * 24);
    assert.equal(monthly.reduce((sum, row) => sum + row.expected, 0), hours);
  }
});

test('daily reference and threshold counts retain each selected year including December 31', () => {
  for (const year of [2023, 2024, 2025]) {
    const {hours} = yearGrid(year), values = Array(hours).fill(10); values[hours - 1] = 100;
    const pm = {year, startUtc: `${year}-01-01T00:00:00Z`, intervalMinutes: 60, standardOffsetMinutes: 0, values};
    const b = pm25Benchmark(pm), counts = thresholdCounts(pm, 35);
    assert.equal(b.expectedDays, year === 2024 ? 366 : 365);
    assert.equal(b.validDays, b.expectedDays);
    assert.equal(counts.hourly.valid, hours); assert.equal(counts.hourly.above, 1);
    assert.equal(counts.dailyValues.at(-1).date, `${year}-12-31`);
    const heat = {startUtc: pm.startUtc, intervalMinutes: 60, utcOffsetHours: 0, values: {temperature: Array(hours).fill(20)}};
    assert.equal(dailyPairs(pm, heat, {basis: 'utc'}).days.length, b.expectedDays);
    assert.equal(dailyPairs(pm, heat, {basis: 'local', utcOffsetMinutes: 540}).days.length, b.expectedDays - 1);
  }
});

test('all timeline sources match hashes, actual years and independent Python daily counts', () => {
  for (const project of ['air-quality', 'air-heat']) {
    const index = read(`../projects/${project}/data/periods.json`);
    assert.deepEqual(index.periods.map(row => row.year), [2023, 2024, 2025]);
    for (const period of index.periods) {
      const manifest = read(`../projects/${project}/${period.manifest}`);
      assert.equal(manifest.year, period.year);
      for (const entry of manifest.records) {
        const paths = project === 'air-quality' ? [{file: entry.file, sha256: entry.sha256}] : [entry.pm, entry.heat];
        for (const source of paths) {
          const url = new URL(`../projects/${project}/${source.file}`, import.meta.url);
          const bytes = readFileSync(url, 'utf8').replaceAll('\r\n', '\n');
          assert.equal(createHash('sha256').update(bytes).digest('hex'), source.sha256);
          const data = JSON.parse(bytes); assert.equal(data.year, period.year);
          assert.equal(Array.isArray(data.values) ? data.values.length : data.values.temperature.length, yearGrid(period.year).hours);
        }
        if (project === 'air-heat') {
          const pm = read(`../projects/${project}/${entry.pm.file}`), heat = read(`../projects/${project}/${entry.heat.file}`);
          for (const basis of ['local', 'utc']) for (const metric of Object.keys(heat.values)) {
            const actual = dailyPairs(pm, heat, {basis, heatMetric: metric, utcOffsetMinutes: entry.utcOffsetHours * 60, from: `${period.year}-01-01`, through: `${period.year}-12-31`});
            assert.equal(actual.days.length, entry.expectedDailyPairs[basis][metric].pairedEligibleDays);
            assert.equal(actual.allDays.length, entry.expectedDailyPairs[basis][metric].completeDays);
          }
        }
      }
    }
  }
});
