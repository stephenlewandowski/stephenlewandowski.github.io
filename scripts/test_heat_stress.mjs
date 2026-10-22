import test from 'node:test';
import assert from 'node:assert/strict';
import {START_2024, HOURS_2024, yearGrid, summarize, quantile, aggregate, counts, monthly, hourlyProfile, utciCategories, exceedanceSteps}
  from '../projects/heat-stress/analysis.mjs';

test('summaries preserve negative temperatures, use finite values and interpolate type-7 quantiles', () => {
  const result = summarize([-20, -10, 0, 10, null, undefined, NaN, Infinity, -Infinity]);
  assert.deepEqual(result, {count: 4, mean: -5, median: -5, p95: 8.499999999999996, max: 10, min: -20});
  assert.equal(quantile([30, 0, 10, 20], .5), 15);
  assert.equal(quantile([null], .95), null);
  assert.deepEqual(summarize([null, NaN]), {count: 0, mean: null, median: null, p95: null, max: null, min: null});
});

test('hourly aggregation retains original hour indices and clamps an inclusive selection', () => {
  assert.deepEqual(aggregate([-10, null, 20, 30], 'hourly', 0, 1, 2), [
    {hour: 1, value: null, count: 0, expected: 1}, {hour: 2, value: 20, count: 1, expected: 1},
  ]);
  assert.equal(aggregate([1, 2], 'hourly', 0, -10, 10).length, 2);
  assert.deepEqual(aggregate([1, 2], 'hourly', 0, 2, 1), []);
});

test('daily means, maxima and minima share the 18-observation rule', () => {
  const values = Array(48).fill(null);
  for (let hour = 0; hour < 18; hour++) values[hour] = hour - 10;
  for (let hour = 24; hour < 41; hour++) values[hour] = 40;
  assert.deepEqual(aggregate(values, 'dailyMean').map(point => point.value), [-1.5, null]);
  assert.deepEqual(aggregate(values, 'dailyMax').map(point => point.value), [7, null]);
  assert.deepEqual(aggregate(values, 'dailyMin').map(point => point.value), [-10, null]);
  assert.deepEqual(aggregate(values, 'dailyMean').map(point => point.count), [18, 17]);
});

test('daily groups use standard time and omit partial boundary days for positive and negative offsets', () => {
  const values = Array.from({length: 72}, (_, hour) => hour);
  const west = aggregate(values, 'dailyMin', -8);
  assert.deepEqual(west.map(point => point.value), [8, 32]);
  const east = aggregate(values, 'dailyMin', 9);
  assert.deepEqual(east.map(point => point.value), [15, 39]);
  assert.deepEqual(aggregate(values, 'dailyMin', 5.5).map(point => point.value), [19, 43]);
  assert.deepEqual(aggregate(values, 'dailyMean', 0, 1, 46), []);
  assert.deepEqual(aggregate(values, 'dailyMin', -8, 9, 70).map(point => point.value), [32]);
});

test('rolling means require complete selected windows and 75% coverage, without reaching before the selection', () => {
  const values = [100, 100, 0, 2, 4, 6, 8, 10, null, null, 12];
  const rolling = aggregate(values, 'rolling8', 0, 2, 10);
  assert.equal(rolling[6].value, null);
  assert.equal(rolling[7].value, 5);
  assert.equal(rolling[7].count, 6);
  assert.equal(rolling[8].value, 7);
  assert.equal(aggregate([1, 2, 3, 4, 5, null, null, null], 'rolling8').at(-1).value, null);
  assert.equal(aggregate(Array(24).fill(-10), 'rolling24').at(-1).value, -10);
  assert.equal(aggregate(Array(24).fill(20), 'rolling24', 0, 1, 23).at(-1).value, null);
});

test('threshold counts are inclusive; percent excludes missing hours and missing values break runs', () => {
  const result = counts([30, 30, null, 30, 29, 30, 30, 30, NaN], 30);
  assert.equal(result.validHours, 7);
  assert.equal(result.hoursAtOrAbove, 6);
  assert.equal(result.percent, 6 / 7 * 100);
  assert.equal(result.longestRun, 3);
  assert.equal(counts([null, NaN], 30).percent, null);
  assert.equal(counts([-10, 0, -5], -5).hoursAtOrAbove, 2);
  assert.equal(counts([30, 30, 30, 30], 30, 0, 1, 2).longestRun, 2);
});

test('day counts distinguish any high hour, a high daily mean and a high daily minimum', () => {
  const values = [...Array(24).fill(20), ...Array(24).fill(30), ...Array(24).fill(40)];
  values[0] = 40;
  const result = counts(values, 30);
  assert.equal(result.validDays, 3);
  assert.equal(result.daysAny, 3);
  assert.equal(result.daysMax, result.daysAny);
  assert.equal(result.daysMean, 2);
  assert.equal(result.daysMin, 2);
  assert.equal(result.validRolling8, 65);
  assert.equal(result.validRolling24, 49);
  assert.equal(counts(values, 30, 0, 1, 70).validDays, 1);
});

test('days with 17 observations do not contribute to daily exceedance denominators', () => {
  const values = Array(48).fill(40);
  for (let hour = 0; hour < 7; hour++) values[hour] = null;
  for (let hour = 24; hour < 30; hour++) values[hour] = null;
  const result = counts(values, 30);
  assert.equal(result.validHours, 35);
  assert.equal(result.validDays, 1);
  assert.equal(result.daysWithHours, 2);
  assert.equal(result.daysAny, 2);
  assert.equal(result.daysMean, 1);
  assert.equal(result.daysMin, 1);
});

test('one observed hot hour counts its date even when a daily mean is ineligible', () => {
  const values = Array(48).fill(null);
  values[12] = 32;
  values[36] = 20;
  const result = counts(values, 30);
  assert.equal(result.validHours, 2);
  assert.equal(result.daysWithHours, 2);
  assert.equal(result.daysAny, 1);
  assert.equal(result.validDays, 0);
  assert.equal(result.daysMean, 0);
  assert.equal(result.daysMin, 0);
  assert.equal(result.daysMax, 0);
  const partial = counts(values, 30, -8, 12, 12);
  assert.equal(partial.daysAny, 1);
  assert.equal(partial.daysWithHours, 1);
  assert.equal(partial.validDays, 0);
});

test('rolling counts count valid overlapping windows with the same selected-range rules', () => {
  const result = counts(Array(32).fill(30), 30, 0, 4, 31);
  assert.equal(result.validHours, 28);
  assert.equal(result.validRolling8, 21);
  assert.equal(result.rolling8AtOrAbove, 21);
  assert.equal(result.validRolling24, 5);
  assert.equal(result.rolling24AtOrAbove, 5);
});

test('2024 UTC monthly denominators include leap day and do not shift with a local-time offset', () => {
  assert.equal(new Date(START_2024).toISOString(), '2024-01-01T00:00:00.000Z');
  const values = Array(HOURS_2024).fill(-5);
  values[744] = null;
  const result = monthly(values, -5, -8);
  assert.equal(result[1].expected, 29 * 24);
  assert.equal(result[1].count, 29 * 24 - 1);
  assert.equal(result[1].mean, -5);
  assert.equal(result[1].max, -5);
  assert.equal(result[1].hoursAtOrAbove, 29 * 24 - 1);
  assert.equal(result.reduce((sum, month) => sum + month.expected, 0), 8784);
  assert.equal(result.reduce((sum, month) => sum + month.count, 0), 8783);
  assert.deepEqual(result, monthly(values, -5, 9));
});

test('non-leap year grids and monthly boundaries match actual 2023 and 2025 calendars', () => {
  for (const year of [2023, 2025]) {
    const grid = yearGrid(year);
    assert.equal(grid.hours, 8760);
    assert.equal(new Date(grid.startUtc).toISOString(), `${year}-01-01T00:00:00.000Z`);
    const values = Array(grid.hours).fill(20);
    const marchStart = (Date.UTC(year, 2, 1) - grid.startUtc) / 3600000;
    values[marchStart] = 40;
    const months = monthly(values, 30, 9, 0, values.length - 1, year);
    assert.equal(months[1].expected, 28 * 24);
    assert.equal(months[1].hoursAtOrAbove, 0);
    assert.equal(months[2].hoursAtOrAbove, 1);
    assert.equal(months.reduce((sum, month) => sum + month.expected, 0), 8760);
    assert.equal(aggregate(values, 'dailyMean').length, 365);
    assert.equal(aggregate(values, 'dailyMean', 9).length, 364);
    assert.equal(aggregate(values, 'dailyMean', -8).length, 364);
  }
  assert.deepEqual(yearGrid(), {year: 2024, startUtc: START_2024, hours: HOURS_2024});
  assert.throws(() => yearGrid(2024.5), RangeError);
});

test('monthly summaries use only the selected hours while retaining missing hours in expected counts', () => {
  const values = Array(HOURS_2024).fill(30);
  values[743] = null;
  const result = monthly(values, 30, 0, 742, 745);
  assert.deepEqual(result[0], {month: 1, count: 1, mean: 30, max: 30, hoursAtOrAbove: 1, expected: 2});
  assert.deepEqual(result[1], {month: 2, count: 2, mean: 30, max: 30, hoursAtOrAbove: 2, expected: 2});
  assert.deepEqual(result[2], {month: 3, count: 0, mean: null, max: null, hoursAtOrAbove: 0, expected: 0});
});

test('hourly profiles follow fixed local time across midnight and preserve negative measurements', () => {
  const west = hourlyProfile([-10, 20, null, 40], 20, -8);
  assert.deepEqual(west[16], {hour: 16, count: 1, hoursAtOrAbove: 0, mean: -10});
  assert.deepEqual(west[17], {hour: 17, count: 1, hoursAtOrAbove: 1, mean: 20});
  assert.equal(west[18].count, 0);
  const east = hourlyProfile(Array(48).fill(30), 30, 9, 15, 38);
  assert.ok(east.every(bin => bin.count === 1 && bin.mean === 30 && bin.hoursAtOrAbove === 1));
  assert.equal(hourlyProfile([30], 30, 5.5)[5].count, 1);
});

test('unknown modes and nonfinite thresholds/offsets are rejected explicitly', () => {
  assert.throws(() => aggregate([1], 'weekly'), RangeError);
  assert.throws(() => aggregate([1], 'hourly', NaN), RangeError);
  assert.throws(() => counts([1], Infinity), RangeError);
  assert.throws(() => monthly([1], NaN), RangeError);
  assert.throws(() => hourlyProfile([1], 20, Infinity), RangeError);
  assert.throws(() => quantile([1], 2), RangeError);
});

test('UTCI category boundaries are upper-closed while user threshold counts remain inclusive', () => {
  const values = [-10, 26, 26.1, 32, 32.1, 38, 38.1, 46, 46.1, null, NaN, Infinity];
  assert.deepEqual(utciCategories(values), {count: 9, bins: [2, 2, 2, 2, 1]});
  assert.deepEqual(utciCategories([26, 32, 38, 46]), {count: 4, bins: [1, 1, 1, 1, 0]});
  assert.deepEqual(utciCategories([null, NaN]), {count: 0, bins: [0, 0, 0, 0, 0]});
  assert.equal(counts([26, 32, 38, 46], 32).hoursAtOrAbove, 3);
});

test('empirical exceedance steps preserve tied frequencies between observed values', () => {
  const values = [20, 20, 20, 30, null, NaN];
  const steps = exceedanceSteps(values);
  assert.deepEqual(steps, [
    {percent: 100, value: 20}, {percent: 25, value: 20},
    {percent: 25, value: 30}, {percent: 0, value: 30},
  ]);
  const at25 = steps.slice(1).find((point, index) => point.value > 25 && steps[index].value < 25);
  assert.equal(at25.percent, counts(values, 25).percent);
  assert.equal(at25.percent, 25);
  assert.deepEqual(exceedanceSteps([-5, -5]), [{percent: 100, value: -5}, {percent: 0, value: -5}]);
  assert.deepEqual(exceedanceSteps([null, NaN]), []);
  assert.equal(counts(values, 20).percent, 100);
  assert.equal(counts(values, 30).percent, 25);
});
