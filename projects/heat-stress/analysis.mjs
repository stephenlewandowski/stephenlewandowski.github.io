/** Metric-independent summaries of hourly values, indexed from 2024-01-01 00:00 UTC. */
export const HOURS_2024 = 8784;
export const START_2024 = Date.UTC(2024, 0, 1);

const HOUR_MS = 3600000;
const valid = value => Number.isFinite(value);

function selectedRange(values, first, last) {
  if (!Number.isInteger(values?.length) || values.length < 0) {
    throw new TypeError('Expected an array of hourly values.');
  }
  if (!Number.isFinite(first) || !Number.isFinite(last)) {
    throw new RangeError('The selected hour bounds must be finite.');
  }
  return {first: Math.max(0, Math.ceil(first)), last: Math.min(values.length - 1, Math.floor(last))};
}

function checkOffset(offsetHours) {
  if (!Number.isFinite(offsetHours)) throw new RangeError('The standard-time offset must be finite.');
}

function checkThreshold(threshold) {
  if (!Number.isFinite(threshold)) throw new RangeError('The comparison threshold must be finite.');
}

function quantileSorted(sorted, probability) {
  if (!sorted.length) return null;
  const position = (sorted.length - 1) * probability;
  const left = Math.floor(position);
  return sorted[left] + (sorted[Math.ceil(position)] - sorted[left]) * (position - left);
}

/** Type-7 quantile of finite values; null, undefined, NaN and infinities are missing. */
export function quantile(values, probability) {
  if (!Number.isFinite(probability) || probability < 0 || probability > 1) {
    throw new RangeError('A quantile probability must be between zero and one.');
  }
  return quantileSorted(Array.from(values).filter(valid).sort((a, b) => a - b), probability);
}

/** Negative temperatures are valid. No rounding or metric-specific limits are applied. */
export function summarize(values) {
  const sorted = Array.from(values).filter(valid).sort((a, b) => a - b);
  if (!sorted.length) return {count: 0, mean: null, median: null, p95: null, max: null, min: null};
  return {
    count: sorted.length,
    mean: sorted.reduce((sum, value) => sum + value, 0) / sorted.length,
    median: quantileSorted(sorted, .5),
    p95: quantileSorted(sorted, .95),
    max: sorted.at(-1),
    min: sorted[0],
  };
}

/**
 * UTCI category counts use the published upper-closed heat-stress intervals:
 * <=26, (26,32], (32,38], (38,46], >46 degrees Celsius. The first bin
 * combines all cold-stress and no-heat-stress values. This categorization is
 * independent of the explorer's user-selected, inclusive >= threshold counts.
 */
export function utciCategories(values) {
  const bins = [0, 0, 0, 0, 0];
  let count = 0;
  for (const value of values) {
    if (!valid(value)) continue;
    count++;
    bins[value <= 26 ? 0 : value <= 32 ? 1 : value <= 38 ? 2 : value <= 46 ? 3 : 4]++;
  }
  return {count, bins};
}

/**
 * Vertices for a stepped empirical exceedance distribution. Each distinct
 * observed value uses the percentage at or above it, retaining tied values
 * together. Horizontal then vertical segments keep frequencies constant
 * between observations. The final horizontal segment reaches zero at the
 * maximum; an exact-threshold marker can disambiguate the jump itself.
 */
export function exceedanceSteps(values) {
  const sorted = Array.from(values).filter(valid).sort((a, b) => a - b);
  const points = [];
  for (let index = 0; index < sorted.length; index++) {
    if (index && sorted[index] === sorted[index - 1]) continue;
    const percent = (sorted.length - index) / sorted.length * 100;
    if (points.length) points.push({percent, value: points.at(-1).value});
    points.push({percent, value: sorted[index]});
  }
  if (points.length) points.push({percent: 0, value: points.at(-1).value});
  return points;
}

/**
 * A day is 24 hourly timestamps in a fixed local standard time, without DST.
 * Fractional offsets are supported. Boundary days are omitted unless all 24
 * expected hourly indices fall within the selected range and supplied array.
 */
function dailyBlocks(values, offsetHours, first, last) {
  const blocks = [];
  if (last < first) return blocks;
  const firstDay = Math.floor((first + offsetHours) / 24);
  const lastDay = Math.floor((last + offsetHours) / 24);
  for (let day = firstDay; day <= lastDay; day++) {
    const start = Math.ceil(day * 24 - offsetHours);
    const end = Math.ceil((day + 1) * 24 - offsetHours) - 1;
    if (start < first || end > last) continue;
    let count = 0;
    let sum = 0;
    let min = Infinity;
    let max = -Infinity;
    for (let hour = start; hour <= end; hour++) {
      const value = values[hour];
      if (!valid(value)) continue;
      count++;
      sum += value;
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
    blocks.push({hour: start + 12, count, expected: 24,
      mean: count >= 18 ? sum / count : null,
      min: count >= 18 ? min : null,
      max: count >= 18 ? max : null});
  }
  return blocks;
}

/**
 * Return {hour, value, count, expected} points for the inclusive selected range.
 * Daily means/maxima/minima require 18 of 24 observations in a complete day.
 * Rolling means trail the current hour, require a complete 8/24-hour window
 * within the selection, and accept at least 75% finite observations. Indices
 * such as UTCI or WBGT must be calculated hourly before calling this function.
 */
export function aggregate(values, mode = 'dailyMean', offsetHours = 0, first = 0, last = values.length - 1) {
  checkOffset(offsetHours);
  ({first, last} = selectedRange(values, first, last));
  if (mode === 'hourly') {
    return Array.from({length: Math.max(0, last - first + 1)}, (_, index) => {
      const hour = first + index;
      const value = valid(values[hour]) ? values[hour] : null;
      return {hour, value, count: value === null ? 0 : 1, expected: 1};
    });
  }
  const dailyKey = {dailyMean: 'mean', dailyMax: 'max', dailyMin: 'min'}[mode];
  if (dailyKey) return dailyBlocks(values, offsetHours, first, last)
    .map(day => ({hour: day.hour, value: day[dailyKey], count: day.count, expected: day.expected}));
  const width = mode === 'rolling8' ? 8 : mode === 'rolling24' ? 24 : null;
  if (width === null) throw new RangeError(`Unknown aggregation mode: ${mode}`);
  let sum = 0;
  let count = 0;
  const points = [];
  for (let hour = first; hour <= last; hour++) {
    if (valid(values[hour])) { sum += values[hour]; count++; }
    const leaving = hour - width;
    if (leaving >= first && valid(values[leaving])) { sum -= values[leaving]; count--; }
    points.push({hour, value: hour - first + 1 >= width && count >= Math.ceil(width * .75)
      ? sum / count : null, count, expected: width});
  }
  return points;
}

/**
 * Inclusive (>=) threshold counts. Percent uses finite hourly observations as
 * its denominator; missing hours break runs. daysWithHours and daysAny count
 * observed dates, including partial boundary dates and dates with sparse data.
 * Daily mean/min/max counts require a complete day and 18 observations.
 * Rolling counts are overlapping windows, not distinct episodes or days.
 */
export function counts(values, threshold, offsetHours = 0, first = 0, last = values.length - 1) {
  checkThreshold(threshold);
  checkOffset(offsetHours);
  ({first, last} = selectedRange(values, first, last));
  let validHours = 0;
  let hoursAtOrAbove = 0;
  let longestRun = 0;
  let run = 0;
  const observedDays = new Set();
  const qualifyingDays = new Set();
  for (let hour = first; hour <= last; hour++) {
    const value = values[hour];
    if (valid(value)) {
      validHours++;
      observedDays.add(Math.floor((hour + offsetHours) / 24));
    }
    if (valid(value) && value >= threshold) {
      hoursAtOrAbove++;
      qualifyingDays.add(Math.floor((hour + offsetHours) / 24));
      run++;
      longestRun = Math.max(longestRun, run);
    } else run = 0;
  }
  const days = dailyBlocks(values, offsetHours, first, last).filter(day => day.mean !== null);
  const rolling8 = aggregate(values, 'rolling8', offsetHours, first, last).filter(point => point.value !== null);
  const rolling24 = aggregate(values, 'rolling24', offsetHours, first, last).filter(point => point.value !== null);
  const daysMax = days.filter(day => day.max >= threshold).length;
  return {
    validHours, hoursAtOrAbove, percent: validHours ? hoursAtOrAbove / validHours * 100 : null,
    longestRun, daysWithHours: observedDays.size, validDays: days.length, daysAny: qualifyingDays.size,
    daysMean: days.filter(day => day.mean >= threshold).length, daysMax,
    daysMin: days.filter(day => day.min >= threshold).length,
    validRolling8: rolling8.length, rolling8AtOrAbove: rolling8.filter(point => point.value >= threshold).length,
    validRolling24: rolling24.length, rolling24AtOrAbove: rolling24.filter(point => point.value >= threshold).length,
  };
}

/**
 * Twelve UTC calendar-month summaries. offsetHours is accepted for the common
 * call signature but does not move UTC month boundaries. expected counts only
 * selected hourly indices; missing observations do not reduce that denominator.
 */
export function monthly(values, threshold, offsetHours = 0, first = 0, last = values.length - 1) {
  checkThreshold(threshold);
  checkOffset(offsetHours);
  ({first, last} = selectedRange(values, first, last));
  return Array.from({length: 12}, (_, month) => {
    const start = Math.max(first, (Date.UTC(2024, month, 1) - START_2024) / HOUR_MS);
    const end = Math.min(last, (Date.UTC(2024, month + 1, 1) - START_2024) / HOUR_MS - 1);
    let count = 0;
    let sum = 0;
    let max = -Infinity;
    let hoursAtOrAbove = 0;
    for (let hour = start; hour <= end; hour++) {
      const value = values[hour];
      if (!valid(value)) continue;
      count++;
      sum += value;
      max = Math.max(max, value);
      if (value >= threshold) hoursAtOrAbove++;
    }
    return {month: month + 1, count, mean: count ? sum / count : null, max: count ? max : null,
      hoursAtOrAbove, expected: Math.max(0, end - start + 1)};
  });
}

/** Mean by fixed local standard-time hour, without daylight-saving adjustment. */
export function hourlyProfile(values, threshold, offsetHours = 0, first = 0, last = values.length - 1) {
  checkThreshold(threshold);
  checkOffset(offsetHours);
  ({first, last} = selectedRange(values, first, last));
  const profile = Array.from({length: 24}, (_, hour) => ({hour, count: 0, sum: 0, hoursAtOrAbove: 0}));
  for (let hour = first; hour <= last; hour++) {
    const value = values[hour];
    if (!valid(value)) continue;
    const localHour = ((Math.floor(hour + offsetHours) % 24) + 24) % 24;
    const bin = profile[localHour];
    bin.count++;
    bin.sum += value;
    if (value >= threshold) bin.hoursAtOrAbove++;
  }
  return profile.map(({sum, ...bin}) => ({...bin, mean: bin.count ? sum / bin.count : null}));
}
