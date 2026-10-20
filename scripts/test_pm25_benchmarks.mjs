import test from 'node:test';
import assert from 'node:assert/strict';
import {localDays, pm25Benchmark, thresholdCounts, PM25_STANDARDS} from '../projects/air-quality/benchmarks.mjs';
import {HOURS_2024, START_2024} from '../projects/air-quality/analysis.mjs';

const record = (values = Array(HOURS_2024).fill(null), extra = {}) => ({id: 'london', year: 2024,
  startUtc: '2024-01-01T00:00:00Z', intervalMinutes: 60, values, ...extra});
const fillDay = (values, day, value, hours = 24) => values.fill(value, day * 24, day * 24 + hours);
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-10, `${actual} != ${expected}`);

test('PM2.5 reference levels retain their distinct annual and daily forms', () => {
  assert.deepEqual(PM25_STANDARDS, {annualPrimary: 9, annualSecondary: 15, daily: 35});
});

test('raw daily means preserve zero and require 18 actual hourly measurements', () => {
  const values = Array(HOURS_2024).fill(null);
  fillDay(values, 0, 0, 18);
  fillDay(values, 1, 80, 17);
  const days = localDays(record(values));
  assert.equal(days.length, 366);
  assert.equal(days[0].mean, 0);
  assert.equal(days[0].validHours, 18);
  assert.equal(days[1].mean, null);
  assert.equal(days[1].validHours, 17);
  assert.equal(days[1].highValueException, false);
});

test('negative, non-finite, absent and null concentrations remain missing', () => {
  const values = Array(HOURS_2024).fill(null);
  values.splice(0, 7, -1, NaN, Infinity, undefined, null, 0, 10);
  const day = localDays(record(values))[0];
  assert.equal(day.validHours, 2);
  assert.equal(day.mean, null);
  const counts = thresholdCounts(record(values), 0, {first: 0, last: 23});
  assert.equal(counts.hourly.valid, 2);
  assert.equal(counts.hourly.above, 1);
});

test('EPA precision truncates hourly inputs before truncating daily means', () => {
  const values = Array(HOURS_2024).fill(null);
  values.fill(1.199, 0, 12);
  values.fill(1.299, 12, 24);
  const raw = localDays(record(values))[0];
  const epa = localDays(record(values), {precision: 'epa'})[0];
  close(raw.mean, 1.249);
  assert.equal(epa.mean, 1.1);
});

test('decimal truncation preserves exact tenths and values immediately below them', () => {
  const values = Array(HOURS_2024).fill(null);
  fillDay(values, 0, 4.1);
  fillDay(values, 1, 4.099999999999999);
  fillDay(values, 2, 1e-7);
  const days = localDays(record(values), {precision: 'epa'});
  assert.equal(days[0].mean, 4.1);
  assert.equal(days[1].mean, 4);
  assert.equal(days[2].mean, 0);
});

test('sparse EPA days use the >=35.5 zero-substitution test and retain its lower bound', () => {
  const values = Array(HOURS_2024).fill(null);
  fillDay(values, 0, 50.2, 17); // 853.4 / 24 = 35.558...
  fillDay(values, 1, 50.1, 17); // 851.7 / 24 = 35.4875
  fillDay(values, 2, 47.4, 18); // A normal valid day uses observed hours.
  const days = localDays(record(values), {precision: 'epa'});
  assert.equal(days[0].mean, 35.5);
  assert.equal(days[0].highValueException, true);
  assert.equal(days[0].validHours, 17);
  assert.equal(days[1].mean, null);
  assert.equal(days[1].highValueException, false);
  assert.equal(days[2].mean, 47.4);
  assert.equal(days[2].highValueException, false);
  assert.equal(localDays(record(values))[0].mean, null);
  const benchmark = pm25Benchmark(record(values));
  assert.equal(benchmark.highValueExceptionDays, 1);
  assert.equal(benchmark.normalValidDays, 1);
  assert.equal(benchmark.validDays, 2);
  assert.equal(thresholdCounts(record(values), 35).daily.valid, 1);
});

test('local standard days use fixed offsets and preserve leap day', () => {
  const values = Array(HOURS_2024).fill(1);
  const seoul = localDays(record(values, {id: 'seoul'}));
  assert.equal(seoul[0].firstHour, -9);
  assert.equal(seoul[0].validHours, 15);
  assert.equal(seoul[0].valid, false);
  assert.equal(seoul[1].firstHour, 15);
  assert.equal(seoul[59].date, '2024-02-29');
  assert.equal(seoul[365].date, '2024-12-31');
  assert.equal(localDays(record(values, {id: 'beijing'}))[0].firstHour, -8);
  const london = localDays(record(values));
  assert.equal(london[182].firstHour, 182 * 24); // Summer remains GMT.
  assert.equal(london[182].validHours, 24);
});

test('supplemental source-local year restores genuine local boundary observations', () => {
  const comparison = record(Array(HOURS_2024).fill(10), {id: 'seoul', localYear: {
    startUtc: '2023-12-31T15:00:00Z', intervalMinutes: 60, values: Array(HOURS_2024).fill(20)}});
  const days = localDays(comparison);
  assert.equal(days[0].firstHour, 0);
  assert.equal(days[0].validHours, 24);
  assert.equal(days[0].mean, 20);
  assert.equal(pm25Benchmark(comparison).validDays, 366);
  assert.equal(thresholdCounts(comparison, 15).hourly.above, 0);
});

test('annual analogue gives each calendar quarter equal weight', () => {
  const values = Array(HOURS_2024).fill(null);
  for (let day = 0; day < 366; day++) {
    const month = new Date(START_2024 + day * 86400000).getUTCMonth();
    fillDay(values, day, Math.floor(month / 3) * 10);
  }
  const result = pm25Benchmark(record(values));
  assert.deepEqual(result.quarters.map(quarter => quarter.expectedDays), [91, 91, 92, 92]);
  assert.deepEqual(result.quarters.map(quarter => quarter.mean), [0, 10, 20, 30]);
  assert.equal(result.annualMean, 15);
  assert.notEqual(result.annualMean, values.reduce((sum, value) => sum + value) / values.length);
});

test('an empty quarter makes the full-year annual analogue unavailable', () => {
  const values = Array(HOURS_2024).fill(null);
  fillDay(values, 0, 10);
  const result = pm25Benchmark(record(values));
  assert.equal(result.annualMean, null);
  assert.equal(result.quarters[0].validDays, 1);
  close(result.quarters[0].capturePercent, 100 / 91);
  assert.equal(result.quarters[1].mean, null);
});

for (const [samples, rank] of [[1, 1], [50, 1], [51, 2], [100, 2], [300, 6], [350, 7], [351, 8], [366, 8]]) {
  test(`EPA 98th percentile uses descending rank ${rank} for ${samples} valid days`, () => {
    const values = Array(HOURS_2024).fill(null);
    for (let day = 0; day < samples; day++) fillDay(values, day, 500 - day);
    const result = pm25Benchmark(record(values));
    assert.equal(result.p98Rank, rank);
    assert.equal(result.p98, 501 - rank);
  });
}

test('a wholly missing year has no percentile or annual mean', () => {
  const result = pm25Benchmark(record());
  assert.equal(result.p98, null);
  assert.equal(result.p98Rank, null);
  assert.equal(result.annualMean, null);
  assert.equal(result.validDays, 0);
});

test('exploratory threshold counts use strict > with unrounded observations', () => {
  const values = Array(HOURS_2024).fill(null);
  fillDay(values, 0, 35);
  fillDay(values, 1, 35.01);
  const result = thresholdCounts(record(values), 35, {first: 0, last: 47});
  assert.deepEqual(result.hourly, {above: 24, valid: 48, expected: 48, percent: 50, longestRun: 24});
  assert.deepEqual(result.daily, {above: 1, valid: 2, expected: 2, percent: 50, longestRun: 1});
  assert.equal(pm25Benchmark(record(values)).daysAbove35, 0); // Both EPA daily means truncate to 35.0.
});

test('decimal summation cannot turn equal concentrations into false exceedances', () => {
  for (const threshold of [0.1, 35.1]) {
    const result = thresholdCounts(record(Array(HOURS_2024).fill(threshold)), threshold);
    for (const mode of ['hourly', 'daily', 'rolling8', 'rolling24']) assert.equal(result[mode].above, 0, mode);
    assert.equal(localDays(record(Array(HOURS_2024).fill(threshold)))[0].mean, threshold);
  }
});

test('a missing hour or day breaks the corresponding consecutive exceedance run', () => {
  const values = Array(HOURS_2024).fill(null);
  values.splice(0, 6, 20, 20, null, 20, 20, 20);
  fillDay(values, 1, 20);
  fillDay(values, 2, 20);
  fillDay(values, 4, 20);
  const result = thresholdCounts(record(values), 10, {first: 0, last: 119});
  assert.equal(result.hourly.longestRun, 48);
  assert.equal(result.daily.longestRun, 2);
  assert.equal(result.daily.valid, 3);
});

test('subranges exclude partial calendar days while rolling ends can use preceding history', () => {
  const result = thresholdCounts(record(Array(HOURS_2024).fill(20)), 10, {first: 12, last: 59});
  assert.equal(result.hourly.expected, 48);
  assert.equal(result.daily.expected, 1);
  assert.equal(result.dailyValues[0].date, '2024-01-02');
  assert.equal(result.rolling8.valid, 48);
  assert.equal(result.rolling24.valid, 37); // First complete source window ends at hour 23.
});

test('rolling completeness follows 75% coverage without filling missing values', () => {
  const values = Array(HOURS_2024).fill(null);
  values.fill(20, 0, 6);
  const result = thresholdCounts(record(values), 10, {first: 0, last: 7});
  assert.equal(result.rolling8.expected, 1);
  assert.equal(result.rolling8.valid, 1);
  assert.equal(result.rolling8.above, 1);
  values[5] = null;
  assert.equal(thresholdCounts(record(values), 10, {first: 0, last: 7}).rolling8.valid, 0);
});

test('full-year monthly hourly denominators cover 8784 hours including leap February', () => {
  const result = thresholdCounts(record(Array(HOURS_2024).fill(20)), 10);
  assert.equal(result.hourly.expected, 8784);
  assert.equal(result.daily.expected, 366);
  assert.equal(result.rolling8.expected, 8784 - 7);
  assert.equal(result.rolling24.expected, 8784 - 23);
  assert.equal(result.monthly[1].expected, 29 * 24);
  assert.equal(result.monthly.reduce((sum, month) => sum + month.valid, 0), 8784);
  assert.equal(result.monthly[0].percent, 100);
});

test('local standard threshold grouping counts boundary days honestly and never merges 2025 hours', () => {
  const result = thresholdCounts(record(Array(HOURS_2024).fill(20), {id: 'seoul'}), 10, {basis: 'local-standard'});
  assert.equal(result.daily.expected, 366);
  assert.equal(result.daily.valid, 365);
  assert.equal(result.hourly.expected, 8784 - 9);
  assert.equal(result.monthly[0].expected, 31 * 24 - 9);
  assert.equal(result.monthly[11].expected, 31 * 24);
  const partial = thresholdCounts(record(Array(HOURS_2024).fill(20), {id: 'seoul'}), 10,
    {first: 0, last: 47, basis: 'local-standard'});
  assert.equal(partial.daily.expected, 1);
  assert.equal(partial.dailyValues[0].date, '2024-01-02');
});

test('empty selections and invalid options do not manufacture data', () => {
  const result = thresholdCounts(record(), 10, {first: 40, last: 23});
  assert.equal(result.hourly.expected, 0);
  assert.equal(result.hourly.percent, null);
  assert.equal(result.daily.expected, 0);
  assert.throws(() => thresholdCounts(record(), NaN), /finite/);
  assert.throws(() => thresholdCounts(record(), 10, {basis: 'daylight-saving'}), /basis/);
  assert.throws(() => localDays(record(), {precision: 'rounded'}), /precision/);
});
