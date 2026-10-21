import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {START_2024, dailyPairs, pearson, spearman, fitAssociation, predict} from '../projects/air-heat/analysis.mjs';

const near = (actual, expected, tolerance = 1e-10) => assert.ok(Math.abs(actual - expected) <= tolerance,
  `${actual} differs from ${expected}`);
const pm = (values, startUtc = '2024-01-01T00:00:00Z') => ({values, startUtc, intervalMinutes: 60});
const heat = (values, startUtc = '2024-01-01T00:00:00Z', utcOffsetHours = 0) =>
  ({values: {temperature: values}, startUtc, intervalMinutes: 60, utcOffsetHours});
const fixture = (x, y, dates = []) => x.map((heatMean, index) => ({heatMean, pmMean: y[index],
  date: dates[index] ?? `2024-01-${String(index + 1).padStart(2, '0')}`, month: Number((dates[index] ?? '2024-01-01').slice(5, 7))}));

test('paired means use exactly the same hours even when separate valid-hour counts differ', () => {
  const p = Array(24).fill(10), h = Array(24).fill(20);
  p[0] = null; p[1] = 1000; h[1] = null; h[0] = -1000;
  const result = dailyPairs(pm(p), heat(h));
  assert.equal(result.days.length, 1);
  assert.deepEqual([result.days[0].pmHours, result.days[0].heatHours, result.days[0].pairedHours], [23, 23, 22]);
  assert.equal(result.days[0].pmMean, 10);
  assert.equal(result.days[0].heatMean, 20);
  assert.equal(result.coverage.pairedHours, 22);
  assert.equal(result.coverage.expectedHours, 24);
});

test('18 paired hours qualify, but 18 separately valid hours can still fail pairing', () => {
  const p = Array(48).fill(10), h = Array(48).fill(20);
  for (let index = 0; index < 6; index++) {p[index] = null; h[index] = null;}
  for (let index = 24; index < 30; index++) p[index] = null;
  for (let index = 30; index < 36; index++) h[index] = null;
  const result = dailyPairs(pm(p), heat(h));
  assert.equal(result.days.length, 1);
  assert.equal(result.days[0].pairedHours, 18);
  assert.equal(result.allDays[1].pmMean, null);
  assert.equal(result.allDays[1].heatMean, null);
  assert.equal(result.allDays[1].pairedHours, 12);
  assert.deepEqual([result.coverage.pmEligibleDays, result.coverage.heatEligibleDays, result.coverage.pairedEligibleDays], [2, 2, 1]);
  assert.equal(result.coverage.excludedPairingDays, 1);
  assert.equal(result.coverage.eligiblePairedHours, 18);
});

test('null, undefined, NaN and infinities are missing; zero PM and negative temperatures remain valid', () => {
  const p = Array(24).fill(0), h = Array(24).fill(-8);
  [null, undefined, NaN, Infinity, -Infinity].forEach((value, index) => {p[index] = value; h[index + 1] = value;});
  const result = dailyPairs(pm(p), heat(h));
  assert.equal(result.days[0].pairedHours, 18);
  assert.equal(result.days[0].pmMean, 0);
  assert.equal(result.days[0].heatMean, -8);
});

test('negative PM concentrations are invalid, while zero concentrations remain paired', () => {
  const p = Array(24).fill(0), h = Array(24).fill(-5);
  p[0] = -1;
  const result = dailyPairs(pm(p), heat(h));
  assert.equal(result.days[0].pairedHours, 23);
  assert.equal(result.days[0].pmMean, 0);
});

test('timestamp alignment handles Seoul station supplement starting nine hours before UTC year', () => {
  const p = Array.from({length: 72}, (_, index) => index);
  const h = Array.from({length: 72}, (_, index) => index + 9);
  const result = dailyPairs(pm(p, '2023-12-31T15:00:00Z'), heat(h), {basis: 'utc'});
  assert.deepEqual(result.days.map(day => day.date), ['2024-01-01', '2024-01-02']);
  near(result.days[0].pmMean, 20.5);
  near(result.days[0].heatMean, 20.5);
  assert.equal(result.days[0].firstUtc, '2024-01-01T00:00:00.000Z');
});

test('fixed local standard days omit partial boundaries for east/west/fractional offsets without DST', () => {
  const values = Array.from({length: 72}, (_, index) => index);
  const east = dailyPairs(pm(values), heat(values, undefined, 9));
  assert.deepEqual(east.days.map(day => day.date), ['2024-01-02', '2024-01-03']);
  assert.equal(east.days[0].firstUtc, '2024-01-01T15:00:00.000Z');
  near(east.days[0].pmMean, 26.5);
  const west = dailyPairs(pm(values), heat(values, undefined, -8));
  assert.deepEqual(west.days.map(day => day.date), ['2024-01-01', '2024-01-02']);
  assert.equal(west.days[0].firstUtc, '2024-01-01T08:00:00.000Z');
  near(west.days[0].heatMean, 19.5);
  const fractional = dailyPairs(pm(values), heat(values, undefined, 5.5));
  assert.equal(fractional.days[0].firstUtc, '2024-01-01T19:00:00.000Z');
  near(fractional.days[0].heatMean, 30.5);
});

test('leap day and inclusive date filters select calendar labels, not UTC clipping endpoints', () => {
  const values = Array(366 * 24).fill(1);
  const result = dailyPairs(pm(values), heat(values, undefined, 9), {from: '2024-02-29', through: '2024-02-29'});
  assert.equal(result.days.length, 1);
  assert.equal(result.days[0].month, 2);
  assert.equal(result.days[0].date, '2024-02-29');
  assert.equal(result.days[0].firstUtc, '2024-02-28T15:00:00.000Z');
  assert.equal(result.days[0].dayIndex, (START_2024 + 59 * 24 * 3600000) / (24 * 3600000));
  assert.equal(dailyPairs(pm(values), heat(values), {basis: 'utc'}).days.length, 366);
  assert.equal(dailyPairs(pm(values), heat(values, undefined, 9)).days.length, 365);
  assert.equal(dailyPairs(pm(values), heat(values), {from: '2024-03-01', through: '2024-02-29'}).days.length, 0);
});

test('record schema, calendar dates, metric presence and minimum-hour controls are validated', () => {
  const values = Array(24).fill(1);
  assert.throws(() => dailyPairs(pm(values), heat(values), {minHours: 25}), RangeError);
  assert.throws(() => dailyPairs(pm(values), heat(values), {basis: 'civil'}), RangeError);
  assert.throws(() => dailyPairs(pm(values), heat(values), {utcOffsetMinutes: NaN}), RangeError);
  assert.throws(() => dailyPairs(pm(values), heat(values), {from: '2024-02-30'}), RangeError);
  assert.throws(() => dailyPairs(pm(values), heat(values), {from: 'nonsense'}), RangeError);
  assert.throws(() => dailyPairs(pm(values), heat(values), {heatMetric: 'missing'}), TypeError);
  assert.throws(() => dailyPairs({...pm(values), intervalMinutes: 30}, heat(values)), RangeError);
  assert.throws(() => dailyPairs(pm(values, '2024-01-01T00:30:00Z'), heat(values)), RangeError);
  assert.equal(dailyPairs(pm([]), heat([])).days.length, 0);
});

test('Pearson and Spearman use joint finite pairs and averaged ranks for ties', () => {
  near(pearson([1, 2, 3], [7, 5, 3]), -1);
  near(spearman([1, 2, 2, 4], [10, 20, 30, 40]), 3 / Math.sqrt(10));
  near(spearman([4, 2, 2, 1], [10, 20, 30, 40]), -3 / Math.sqrt(10));
  near(pearson([1, null, 2, Infinity], [3, 99, 5, 999]), 1);
  assert.equal(pearson([1, 1], [2, 3]), null);
  assert.equal(spearman([1, 1], [2, 3]), null);
  assert.equal(pearson([], []), null);
  assert.throws(() => pearson([1], []), RangeError);
});

test('linear OLS matches independently computed coefficients, residuals, leverage, R² and Cook distance', () => {
  // Hand calculation: xbar=2, ybar=2.4, Sxx=10, Sxy=9, Syy=11.2.
  const result = fitAssociation(fixture([0, 1, 2, 3, 4], [1, 2, 1, 3, 5]));
  assert.equal(result.available, true);
  assert.equal(result.rank, 2);
  near(result.slope, .9);
  near(result.slopePer10, 9);
  near(result.intercept, .6);
  near(result.residualSumSquares, 3.1);
  near(result.r2, 8.1 / 11.2);
  near(result.r, 9 / Math.sqrt(112));
  near(result.predictions[4].fitted, 4.2);
  near(result.predictions[4].residual, .8);
  near(result.predictions[4].leverage, .6);
  near(result.predictions.reduce((sum, row) => sum + row.leverage, 0), 2);
  near(result.predictions[4].cooksDistance, .64 / (2 * (3.1 / 3)) * .6 / .16);
  near(predict(result, 10), 9.6);
  assert.equal(result.lag1.pairs, 4);
  assert.equal(result.residualDf, 3);
});

test('centered/scaled quadratic recovers an exact curve and remains stable at a large x origin', () => {
  const x = [-2, -1, 0, 1, 2], y = x.map(value => 3 + 2 * value - .5 * value ** 2);
  const result = fitAssociation(fixture(x, y), {model: 'quadratic'});
  assert.equal(result.available, true);
  near(result.r2, 1);
  near(result.slope, 2);
  near(result.slopeAt, 0);
  near(predict(result, 3), 4.5);
  assert.equal(result.maxCooksDistance, 0);
  const shifted = fitAssociation(fixture(x.map(value => value + 1e8), y), {model: 'quadratic'});
  near(predict(shifted, 1e8 + 3), 4.5);
});

test('month adjustment separates within-month association from the pooled seasonal relationship', () => {
  const days = fixture([0, 1, 2, 10, 11, 12], [10, 11, 12, 0, 1, 2],
    ['2024-01-01', '2024-01-02', '2024-01-03', '2024-07-01', '2024-07-02', '2024-07-03']);
  assert.ok(fitAssociation(days).slope < 0);
  const adjusted = fitAssociation(days, {model: 'monthAdjusted'});
  near(adjusted.slope, 1);
  near(adjusted.r2, 1);
  near(adjusted.rWithin, 1);
  near(adjusted.rhoWithin, 1);
  assert.ok(adjusted.r < 0);
  assert.equal(adjusted.r2Basis, 'within-month');
  assert.equal(adjusted.parameterCount, 3);
  near(predict(adjusted, 1, 1), 11);
  near(predict(adjusted, 11, 7), 1);
  assert.equal(predict(adjusted, 11), null);
  near(adjusted.predictions[0].xDeparture, -1);
  near(adjusted.predictions[0].yDeparture, -1);
  near(adjusted.predictions[0].fittedDeparture, -1);
  assert.equal(adjusted.lag1.pairs, 4);
});

test('constant and singular designs are explicit, while constant PM retains a zero slope with undefined correlation', () => {
  assert.equal(fitAssociation(fixture([1, 1, 1, 1], [1, 2, 3, 4])).available, false);
  const twoValues = fitAssociation(fixture([0, 0, 1, 1], [1, 2, 3, 4]), {model: 'quadratic'});
  assert.equal(twoValues.available, false);
  assert.equal(twoValues.rank, 2);
  const months = fixture([1, 1, 1, 2, 2, 2], [1, 2, 3, 4, 5, 6],
    ['2024-01-01', '2024-01-02', '2024-01-03', '2024-02-01', '2024-02-02', '2024-02-03']);
  assert.equal(fitAssociation(months, {model: 'monthAdjusted'}).available, false);
  const constantAcrossMonths = fitAssociation(months.map(day => ({...day, heatMean: 1})), {model: 'monthAdjusted'});
  assert.equal(constantAcrossMonths.available, false);
  assert.equal(constantAcrossMonths.rank, 2);
  const constantPM = fitAssociation(fixture([1, 2, 3, 4], [2, 2, 2, 2]));
  assert.equal(constantPM.available, true);
  near(constantPM.slope, 0);
  assert.equal(constantPM.r, null);
  assert.equal(constantPM.r2, null);
});

test('insufficient data, missing pairs and invalid models do not yield a misleading fit', () => {
  assert.equal(fitAssociation([]).available, false);
  assert.equal(fitAssociation(fixture([1, 2], [2, 3])).available, false);
  assert.equal(fitAssociation(fixture([1, 2, 3], [2, 3, 4]), {model: 'quadratic'}).available, false);
  assert.equal(fitAssociation(fixture([1, 2, null, 3], [2, 3, 99, Infinity])).n, 2);
  assert.throws(() => fitAssociation([], {model: 'spline'}), RangeError);
  assert.throws(() => fitAssociation([{heatMean: 1, pmMean: 2, month: 0}], {model: 'monthAdjusted'}), RangeError);
  assert.equal(predict({available: false}, 2), null);
});

test('residual lag-1 diagnostic uses consecutive calendar dates, not adjacent selected rows', () => {
  const days = fixture([0, 1, 2, 3, 4], [1, 2, 1, 3, 5],
    ['2024-01-01', '2024-01-02', '2024-01-04', '2024-01-05', '2024-01-09']);
  const result = fitAssociation(days);
  assert.equal(result.lag1.pairs, 2);
  near(result.lag1.r, 1);
  const reversed = fitAssociation([...days].reverse());
  assert.equal(reversed.lag1.pairs, 2);
  near(reversed.lag1.r, 1);
});

test('all cities, metrics and calendars match independently computed Python coverage and associations', () => {
  const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
  const manifest = read('../projects/air-heat/data/manifest.json');
  for (const record of manifest.records) {
    const p = read(`../projects/air-heat/${record.pm.file}`);
    const h = read(`../projects/air-heat/${record.heat.file}`);
    for (const basis of ['local', 'utc']) {
      for (const metric of Object.keys(manifest.metrics)) {
        const expected = record.expectedDailyPairs[basis][metric];
        const result = dailyPairs(p, h, {basis, heatMetric: metric, utcOffsetMinutes: record.utcOffsetHours * 60,
          from: '2024-01-01', through: '2024-12-31'});
        const context = `${record.id}/${basis}/${metric}`;
        for (const field of ['completeDays', 'pmEligibleDays', 'heatEligibleDays', 'pairedEligibleDays', 'expectedHours', 'pmHours', 'heatHours', 'pairedHours', 'eligiblePairedHours']) {
          assert.equal(result.coverage[field], expected[field], `${context} ${field}`);
        }
        const monthlyDays = Array.from({length: 12}, (_, index) => result.days.filter(day => day.month === index + 1).length);
        assert.deepEqual(monthlyDays, expected.monthlyPairedDays, `${context} months`);
        near(fitAssociation(result.days).r, expected.rawPearsonR, 5.1e-9);
        near(fitAssociation(result.days, {model: 'monthAdjusted'}).rWithin, expected.withinMonthPearsonR, 5.1e-9);
      }
    }
  }
});
