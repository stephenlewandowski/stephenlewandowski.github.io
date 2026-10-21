import test from 'node:test';
import assert from 'node:assert/strict';
import {hourlyJoint} from '../projects/air-heat/hourly.mjs';

const pm = (values, startUtc = '2024-01-01T00:00:00Z') => ({values, startUtc, intervalMinutes: 60});
const heat = (values, startUtc = '2024-01-01T00:00:00Z', utcOffsetHours = 0) =>
  ({values: {temperature: values}, startUtc, intervalMinutes: 60, utcOffsetHours});
const options = {pmThreshold: 35, heatThreshold: 30};

test('hourly denominator uses shared finite observations; threshold equality is included', () => {
  const result = hourlyJoint(pm([35, 35, 0, null, -1, 100, Infinity]), heat([30, 29, 30, 30, 30, null, 30]), options);
  assert.deepEqual([result.expectedHours, result.pairedHours, result.missingHours], [7, 3, 4]);
  assert.deepEqual([result.pmHoursAbove, result.thermalHoursMeeting, result.bothHours], [2, 2, 1]);
  assert.equal(result.fractionOfPaired, 1 / 3);
  assert.deepEqual([result.pmOnlyHours, result.thermalOnlyHours, result.neitherHours], [1, 1, 0]);
});

test('consecutive samples cross midnight and observed-false neighbours do not censor', () => {
  const result = hourlyJoint(pm([0, 40, 40, 40, 0], '2024-01-01T22:00:00Z'),
    heat([32, 32, 32, 32, 32], '2024-01-01T22:00:00Z'), options);
  assert.equal(result.eventCount, 1);
  assert.equal(result.longestRunHours, 3);
  assert.equal(result.daysWithBoth, 2);
  assert.equal(result.events[0].startUtc, '2024-01-01T23:00:00.000Z');
  assert.equal(result.events[0].endUtc, '2024-01-02T01:00:00.000Z');
  assert.equal(result.events[0].censored, false);
  assert.equal(result.events[0].leftCensorReason, null);
  assert.equal(result.events[0].rightCensorReason, null);
  assert.equal(result.runHistogram.find(bin => bin.label === '2–3').events, 1);
  assert.equal(result.runHistogram.reduce((total, bin) => total + bin.hours, 0), 3);
});

test('missing hours break runs and censor continuation; zero is an observed below-threshold value', () => {
  const result = hourlyJoint(pm([40, 40, null, 40, 0, 40]), heat([32, 32, 32, 32, 32, 32]), options);
  assert.deepEqual(result.events.map(event => event.durationHours), [2, 1, 1]);
  assert.deepEqual(result.events.map(event => [event.leftCensorReason, event.rightCensorReason]),
    [['record', 'missing'], ['missing', null], [null, 'record']]);
  assert.equal(result.censoredEventCount, 3);
  assert.equal(result.longestRunHours, 2);
});

test('real timestamps align archives with different starts rather than matching array indices', () => {
  const result = hourlyJoint(pm([0, 40, 40, 0], '2023-12-31T23:00:00Z'), heat([31, 31, 31]), options);
  assert.equal(result.expectedHours, 3);
  assert.equal(result.bothHours, 2);
  assert.equal(result.events[0].startUtc, '2024-01-01T00:00:00.000Z');
  assert.equal(result.events[0].leftCensorReason, 'record');
  assert.equal(result.events[0].rightCensorReason, null);
});

test('inclusive local calendar bounds retain partial endpoint days and report them', () => {
  const values = Array(48).fill(40);
  const result = hourlyJoint(pm(values), heat(values, undefined, 9), {...options, from: '2024-01-01', through: '2024-01-02'});
  assert.equal(result.expectedHours, 39);
  assert.deepEqual(result.days.map(day => [day.date, day.expectedHours]), [['2024-01-01', 15], ['2024-01-02', 24]]);
  assert.equal(result.partialBoundaryDays.length, 1);
  assert.equal(result.longestRunHours, 39);
  assert.equal(result.events[0].startLocal, '2024-01-01 09:00');
  assert.equal(result.events[0].rightCensorReason, 'selection');
  const utc = hourlyJoint(pm(values), heat(values, undefined, 9), {...options, basis: 'utc', from: '2024-01-01', through: '2024-01-01'});
  assert.equal(utc.expectedHours, 24);
  assert.equal(utc.partialBoundaryDays.length, 0);
  assert.equal(utc.utcOffsetMinutes, 0);
});

test('negative and fractional fixed offsets assign calendar labels without changing UTC runs', () => {
  const values = Array(24).fill(40);
  const west = hourlyJoint(pm(values), heat(values, undefined, -8), options);
  assert.deepEqual(west.days.map(day => [day.date, day.expectedHours]), [['2023-12-31', 8], ['2024-01-01', 16]]);
  assert.equal(west.longestRunHours, 24);
  const fractional = hourlyJoint(pm(values), heat(values, undefined, 5.5), {...options, from: '2024-01-01', through: '2024-01-01'});
  assert.equal(fractional.expectedHours, 19);
  assert.equal(fractional.events[0].startLocal, '2024-01-01 05:30');
  assert.equal(fractional.events[0].endLocal, '2024-01-01 23:30');
});

test('season boundary interrupts a run and reports a clipped event', () => {
  const values = Array(48).fill(40);
  const result = hourlyJoint(pm(values, '2024-02-29T00:00:00Z'), heat(values, '2024-02-29T00:00:00Z'), {...options, season: 'MAM'});
  assert.equal(result.expectedHours, 24);
  assert.equal(result.events[0].startUtc, '2024-03-01T00:00:00.000Z');
  assert.equal(result.events[0].leftCensorReason, 'selection');
  assert.equal(result.events[0].rightCensorReason, 'record');
});

test('below direction includes equality and retained subfreezing temperatures', () => {
  const result = hourlyJoint(pm([35, 35, 35, 0]), heat([-1, 0, 1, -1]), {...options, heatThreshold: 0, direction: 'below'});
  assert.equal(result.bothHours, 2);
  assert.equal(result.thermalHoursMeeting, 3);
  assert.equal(result.longestRunHours, 2);
});

test('monthly totals split counts at midnight without splitting continuous events', () => {
  const result = hourlyJoint(pm([40, 40, 40, 40], '2024-01-31T22:00:00Z'),
    heat([40, 40, 40, 40], '2024-01-31T22:00:00Z'), options);
  assert.equal(result.eventCount, 1);
  assert.deepEqual(result.months.map(row => [row.month, row.bothHours, row.daysWithBoth]), [['2024-01', 2, 1], ['2024-02', 2, 1]]);
  assert.equal(result.months.reduce((total, row) => total + row.bothHours, 0), result.bothHours);
});

test('empty intersection, excluded periods, and all-missing records have explicit empty results', () => {
  const disjoint = hourlyJoint(pm([40]), heat([40], '2024-02-01T00:00:00Z'), options);
  assert.equal(disjoint.expectedHours, 0);
  assert.equal(disjoint.fractionOfPaired, null);
  assert.equal(disjoint.coverageStartUtc, null);
  assert.equal(disjoint.events.length, 0);
  const excluded = hourlyJoint(pm([40]), heat([40]), {...options, from: '2024-02-01'});
  assert.equal(excluded.expectedHours, 0);
  const missing = hourlyJoint(pm([null, NaN]), heat([40, 40]), options);
  assert.equal(missing.expectedHours, 2);
  assert.equal(missing.pairedHours, 0);
  assert.equal(missing.fractionOfPaired, null);
  assert.equal(missing.longestRunHours, 0);
});

test('invalid dates, reversed dates, non-hourly records, season and threshold inputs are rejected', () => {
  for (const invalid of [{from: '2024-02-30'}, {from: '2024-03-01', through: '2024-02-01'}, {basis: 'civil'},
    {season: 'summer'}, {direction: 'over'}, {pmThreshold: -1}, {heatThreshold: NaN}, {utcOffsetMinutes: 1000}]) {
    assert.throws(() => hourlyJoint(pm([40]), heat([40]), {...options, ...invalid}), RangeError);
  }
  assert.throws(() => hourlyJoint({...pm([40]), intervalMinutes: 30}, heat([40]), options), RangeError);
  assert.throws(() => hourlyJoint(pm([40], '2024-01-01T00:30:00Z'), heat([40]), options), RangeError);
});
