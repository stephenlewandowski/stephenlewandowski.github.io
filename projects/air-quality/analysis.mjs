export const HOURS_2024 = 8784;
export const START_2024 = Date.UTC(2024, 0, 1);

export function yearGrid(year = 2024) {
  if (!Number.isInteger(year) || year < 1900 || year > 2100) throw new RangeError('A supported calendar year is required.');
  const start = Date.UTC(year, 0, 1);
  return {year, start, hours: (Date.UTC(year + 1, 0, 1) - start) / 3600000};
}

export function summarize(values) {
  const valid = values.filter(value => Number.isFinite(value) && value >= 0).sort((a, b) => a - b);
  if (!valid.length) return {count: 0, mean: null, median: null, p95: null, max: null};
  const quantile = p => {
    const position = (valid.length - 1) * p;
    const left = Math.floor(position);
    return valid[left] + (valid[Math.ceil(position)] - valid[left]) * (position - left);
  };
  return {count: valid.length, mean: valid.reduce((sum, value) => sum + value, 0) / valid.length,
    median: quantile(.5), p95: quantile(.95), max: valid.at(-1)};
}

// A complete window must exist; at least 75% of its hourly values must be valid.
export function aggregate(values, mode = 'daily') {
  const clean = values.map(value => Number.isFinite(value) && value >= 0 ? value : null);
  if (mode === 'hourly') return clean.map((value, hour) => ({hour, value, count: value === null ? 0 : 1, expected: 1}));
  if (mode === 'daily') {
    const points = [];
    for (let hour = 0; hour < clean.length; hour += 24) {
      const block = clean.slice(hour, hour + 24);
      const valid = block.filter(value => value !== null);
      points.push({hour: hour + 12, value: block.length === 24 && valid.length >= 18
        ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null, count: valid.length, expected: 24});
    }
    return points;
  }
  const width = mode === 'rolling8' ? 8 : mode === 'rolling24' ? 24 : null;
  if (width === null) throw new Error(`Unknown averaging mode: ${mode}`);
  let sum = 0;
  let count = 0;
  return clean.map((value, hour) => {
    if (value !== null) { sum += value; count++; }
    if (hour >= width && clean[hour - width] !== null) { sum -= clean[hour - width]; count--; }
    return {hour, value: hour >= width - 1 && count >= Math.ceil(width * .75) ? sum / count : null,
      count, expected: width};
  });
}

export function monthlySummary(values, year = 2024) {
  const {start} = yearGrid(year);
  return Array.from({length: 12}, (_, month) => {
    const first = (Date.UTC(year, month, 1) - start) / 3600000;
    const last = (Date.UTC(year, month + 1, 1) - start) / 3600000;
    const statistics = summarize(values.slice(first, last));
    return {month: month + 1, expected: last - first, ...statistics};
  });
}
