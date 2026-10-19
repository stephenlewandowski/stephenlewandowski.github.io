import test from 'node:test';
import assert from 'node:assert/strict';
import {aggregate, summarize, monthlySummary, HOURS_2024} from '../projects/air-quality/analysis.mjs';

test('daily means require 18 of 24 values and retain measured zero', () => {
  const values = Array(48).fill(null);
  for (let i = 0; i < 18; i++) values[i] = 0;
  for (let i = 24; i < 41; i++) values[i] = 12;
  const points = aggregate(values, 'daily');
  assert.equal(points[0].value, 0);
  assert.equal(points[0].count, 18);
  assert.equal(points[1].value, null);
});

test('8-hour trailing mean uses current and previous seven hours, without a partial starting window', () => {
  const points = aggregate([1, 2, 3, 4, 5, 6, 7, 8, 9], 'rolling8');
  assert.equal(points[6].value, null);
  assert.equal(points[7].value, 4.5);
  assert.equal(points[8].value, 5.5);
});

test('rolling mean rejects insufficient coverage and treats negative inputs as invalid', () => {
  assert.equal(aggregate([1, 2, 3, 4, 5, null, null, null], 'rolling8')[7].value, null);
  assert.equal(aggregate([0, 2, 4, 6, 8, 10, null, -999], 'rolling8')[7].value, 5);
});

test('summary excludes missing and negative values, preserves zero and interpolates percentiles', () => {
  const result = summarize([null, -999, 0, 10, 20, 30]);
  assert.equal(result.count, 4);
  assert.equal(result.mean, 15);
  assert.equal(result.median, 15);
  assert.ok(Math.abs(result.p95 - 28.5) < 1e-10);
  assert.equal(summarize([null]).mean, null);
});

test('2024 monthly coverage includes leap day without dropping or duplicating hours', () => {
  const months = monthlySummary(Array(HOURS_2024).fill(1));
  assert.equal(months[1].expected, 29 * 24);
  assert.equal(months.reduce((sum, month) => sum + month.count, 0), 8784);
  assert.ok(months.every(month => month.mean === 1 && month.count === month.expected));
});
