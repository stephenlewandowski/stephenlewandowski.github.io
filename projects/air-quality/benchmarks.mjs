import {aggregate, HOURS_2024, START_2024} from './analysis.mjs';

// Concentration units throughout this module are micrograms per cubic metre.
// These are standard levels, not classifications of this one-year dataset.
export const PM25_STANDARDS = Object.freeze({annualPrimary: 9, annualSecondary: 15, daily: 35});

const HOUR = 3600000;
const DAY = 24 * HOUR;
const OFFSETS = Object.freeze({seoul: 540, beijing: 480, london: 0,
  'Asia/Seoul': 540, 'Asia/Shanghai': 480, 'Europe/London': 0});
const validConcentration = value => Number.isFinite(value) && value >= 0;
const mean = values => values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;

function standardOffset(record) {
  const offset = record.standardOffsetMinutes ?? OFFSETS[record.id] ?? OFFSETS[record.timeZone]
    ?? record.timeConvention?.source_utc_offset_minutes;
  if (!Number.isFinite(offset) || !Number.isInteger(offset / 60)) {
    throw new Error('An explicit whole-hour local standard time offset is required');
  }
  return offset;
}

function sourceGrid(record, useLocalYear = true) {
  const source = useLocalYear && record.localYear ? record.localYear : record;
  const start = source.startUtc ? Date.parse(source.startUtc) : START_2024;
  if (!Array.isArray(source.values) || !Number.isFinite(start)
    || (source.intervalMinutes !== undefined && source.intervalMinutes !== 60)
    || start % HOUR !== 0) throw new Error('Expected an hourly concentration grid');
  return {values: source.values, start};
}

// Convert the supplied decimal representation to integer tenths. String slicing
// avoids turning a decimal boundary into the preceding tenth through binary
// floating-point multiplication. Values just below a boundary still truncate.
function integerTenths(value) {
  const [coefficient, exponent = '0'] = String(value).toLowerCase().split('e');
  const [whole, fraction = ''] = coefficient.split('.');
  const digits = whole + fraction;
  const length = whole.length + Number(exponent) + 1;
  return length <= 0 ? 0 : Number(digits.slice(0, length).padEnd(length, '0'));
}

// Accumulate the complete supplied decimal values in common integer units.
// This preserves source precision while avoiding false threshold crossings
// such as summing 24 readings of 0.1 into a mean of 0.10000000000000003.
function decimalGrid(values) {
  let scale = 0;
  const parts = values.map(value => {
    if (!validConcentration(value)) return null;
    const [coefficient, exponent = '0'] = String(value).toLowerCase().split('e');
    const [whole, fraction = ''] = coefficient.split('.');
    const item = {integer: BigInt(whole + fraction), scale: fraction.length - Number(exponent)};
    scale = Math.max(scale, item.scale);
    return item;
  });
  return {scale, values: parts.map(part => part === null ? null
    : part.integer * 10n ** BigInt(scale - part.scale))};
}

function decimalMean(sum, count, scale) {
  if (!count) return null;
  // Keep 25 guard digits in integer source units before the final conversion
  // to Number, rather than rounding observations or introducing a tolerance.
  return Number(`${sum * 10n ** 25n / BigInt(count)}e-${scale + 25}`);
}

function calendarDays(record, {precision = 'raw', offset = standardOffset(record), useLocalYear = true} = {}) {
  if (!['raw', 'epa'].includes(precision)) throw new Error(`Unknown precision: ${precision}`);
  const {values, start} = sourceGrid(record, useLocalYear);
  const decimal = precision === 'raw' ? decimalGrid(values) : null;
  const year = record.year ?? 2024;
  const firstDate = Date.UTC(year, 0, 1);
  const nextYear = Date.UTC(year + 1, 0, 1);
  return Array.from({length: (nextYear - firstDate) / DAY}, (_, day) => {
    const date = new Date(firstDate + day * DAY);
    const firstHour = (date.getTime() - offset * 60000 - start) / HOUR;
    const observed = [];
    let rawSum = 0n;
    for (let hour = firstHour; hour < firstHour + 24; hour++) {
      if (validConcentration(values[hour])) {
        observed.push(values[hour]);
        if (decimal) rawSum += decimal.values[hour];
      }
    }
    const normalValid = observed.length >= 18;
    let value = null;
    let highValueException = false;
    if (precision === 'epa') {
      const sumTenths = observed.reduce((sum, observation) => sum + integerTenths(observation), 0);
      // Appendix N section 3(c): sparse days can qualify when the zero-filled
      // 24-hour lower bound is at least 35.5. Preserve that conservative value
      // and disclose the exception; this does not invent hourly observations.
      highValueException = !normalValid && sumTenths >= 355 * 24;
      if (normalValid || highValueException) {
        value = Math.floor(sumTenths / (normalValid ? observed.length : 24)) / 10;
      }
    } else if (normalValid) value = decimalMean(rawSum, observed.length, decimal.scale);
    const month = date.getUTCMonth() + 1;
    return {day, date: date.toISOString().slice(0, 10), month, quarter: Math.ceil(month / 3),
      mean: value, validHours: observed.length, expectedHours: 24, valid: value !== null,
      highValueException, firstHour, lastHour: firstHour + 23};
  });
}

/**
 * All calendar days of record.year (2024 by default), midnight to midnight in
 * fixed local STANDARD time: Seoul UTC+9, Beijing UTC+8, London UTC+0 (no DST).
 * A supplemental record.localYear={startUtc,intervalMinutes:60,values} is used
 * when supplied, preserving genuine boundary measurements outside the UTC year.
 * Missing boundary hours otherwise remain missing. `day` is zero based;
 * firstHour/lastHour refer to the chosen source grid and may lie outside it.
 *
 * Raw means need 18 observations. EPA means truncate hourly inputs and daily
 * means to tenths and additionally admit the conservative sparse-day exception
 * described in Appendix N section 3(c). No annual/design-value rounding occurs.
 */
export function localDays(record, {precision = 'raw'} = {}) {
  return calendarDays(record, {precision});
}

/**
 * One-year analogues of Appendix N calculations for continuous daily sampling.
 * AnnualMean gives each of the four quarterly daily means equal weight; it is
 * null if a quarter has no valid day. P98 is the ceil(N/50)th highest valid day,
 * following Appendix N Table 1, rather than an interpolated percentile.
 * Capture rates are descriptive, unrounded percentages. These calculations
 * neither establish site eligibility nor produce the required three-year DVs.
 * Source: https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-50/appendix-Appendix%20N%20to%20Part%2050
 */
export function pm25Benchmark(record) {
  const daily = localDays(record, {precision: 'epa'});
  const valid = daily.filter(day => day.valid);
  const quarters = Array.from({length: 4}, (_, index) => {
    const days = daily.filter(day => day.quarter === index + 1);
    const values = days.filter(day => day.valid).map(day => day.mean);
    return {quarter: index + 1, expectedDays: days.length, validDays: values.length,
      capturePercent: 100 * values.length / days.length, mean: mean(values)};
  });
  const sorted = valid.map(day => day.mean).sort((a, b) => b - a);
  const p98Rank = sorted.length ? Math.ceil(sorted.length / 50) : null;
  const highValueExceptionDays = valid.filter(day => day.highValueException).length;
  return {daily, annualMean: quarters.every(quarter => quarter.mean !== null)
      ? mean(quarters.map(quarter => quarter.mean)) : null,
    quarters, p98: p98Rank === null ? null : sorted[p98Rank - 1], p98Rank,
    validDays: valid.length, expectedDays: daily.length,
    daysAbove35: valid.filter(day => day.mean > PM25_STANDARDS.daily).length,
    highValueExceptionDays, normalValidDays: valid.length - highValueExceptionDays};
}

function countValues(values, threshold) {
  let above = 0;
  let valid = 0;
  let run = 0;
  let longestRun = 0;
  for (const value of values) {
    if (validConcentration(value)) valid++;
    if (validConcentration(value) && value > threshold) {
      above++;
      longestRun = Math.max(longestRun, ++run);
    } else run = 0; // A missing observation cannot join two exceedance runs.
  }
  return {above, valid, expected: values.length, percent: valid ? above / valid * 100 : null, longestRun};
}

/**
 * Literal, strict `>` counts using unrounded concentrations. first/last are
 * inclusive indices in record.values, never in the supplemental localYear grid.
 * basis changes calendar grouping; local-standard additionally restricts all
 * eligible instants to the stated local calendar year. No DST is applied.
 *
 * Daily values require the normal 18-hour rule. A selected subrange includes
 * only calendar days wholly within its hours; choosing the entire source grid
 * includes every calendar day in the year, with missing boundary hours tested
 * normally. Rolling means use the existing 75%-coverage rule and count window
 * ENDS within the selected range. History before first is used if available.
 * expected rolling ends exclude windows preceding the start of the source grid.
 * monthly reports hourly counts in each calendar month; dailyValues contains
 * the eligible raw day objects. Percent denominators are valid observations.
 */
export function thresholdCounts(record, threshold, {first = 0, last = HOURS_2024 - 1, basis = 'utc'} = {}) {
  if (!Number.isFinite(threshold)) throw new Error('The threshold must be finite');
  if (!['utc', 'local-standard'].includes(basis)) throw new Error(`Unknown calendar basis: ${basis}`);
  if (!Number.isFinite(first) || !Number.isFinite(last)) throw new Error('The selected hour indices must be finite');
  const {values, start} = sourceGrid(record, false);
  const decimal = decimalGrid(values);
  const sums = [0n];
  for (const value of decimal.values) sums.push(sums.at(-1) + (value ?? 0n));
  const offset = basis === 'utc' ? 0 : standardOffset(record);
  const year = record.year ?? 2024;
  const begin = Math.max(0, Math.ceil(first));
  const end = Math.min(values.length - 1, Math.floor(last));
  const selected = [];
  const months = Array.from({length: 12}, () => []);
  for (let hour = begin; hour <= end; hour++) {
    const date = new Date(start + hour * HOUR + offset * 60000);
    if (date.getUTCFullYear() !== year) continue;
    selected.push(hour);
    months[date.getUTCMonth()].push(values[hour]);
  }
  const fullGrid = begin === 0 && end === values.length - 1;
  const dailyValues = calendarDays(record, {offset, useLocalYear: false}).filter(day => fullGrid
    || day.firstHour >= begin && day.lastHour <= end);
  const result = {hourly: countValues(selected.map(hour => values[hour]), threshold),
    daily: countValues(dailyValues.map(day => day.mean), threshold),
    monthly: months.map((values, index) => ({month: index + 1, ...countValues(values, threshold)})),
    dailyValues};
  for (const [mode, width] of [['rolling8', 8], ['rolling24', 24]]) {
    const points = aggregate(values, mode);
    result[mode] = countValues(selected.filter(hour => hour >= width - 1).map(hour => points[hour].value === null
      ? null : decimalMean(sums[hour + 1] - sums[hour + 1 - width], points[hour].count, decimal.scale)), threshold);
  }
  return result;
}
