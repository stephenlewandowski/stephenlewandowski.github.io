/** Daily exposure pairing and descriptive associations. No health outcomes or causal effects are modeled. */
export const START_2024 = Date.UTC(2024, 0, 1);
const HOUR = 3600000;
const DAY = 24 * HOUR;
const finite = Number.isFinite;
const mean = values => values.reduce((sum, value) => sum + value, 0) / values.length;
const sumSquares = values => values.reduce((sum, value) => sum + value * value, 0);
const dot = (left, right) => left.reduce((sum, value, index) => sum + value * right[index], 0);

function hourlyRecord(record, values) {
  if (!values || !Number.isInteger(values.length)) throw new TypeError('An hourly value array is required.');
  const start = record.startUtc === undefined ? START_2024 : Date.parse(record.startUtc);
  if (!finite(start) || start % HOUR !== 0) throw new RangeError('The hourly record must start on a valid UTC hour.');
  if (record.intervalMinutes !== undefined && record.intervalMinutes !== 60) throw new RangeError('Only hourly records are supported.');
  return {values, start, end: start + (values.length - 1) * HOUR};
}

function dateBound(value, name) {
  if (value === undefined || value === null || value === '') return null;
  const parsed = Date.parse(`${value}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !finite(parsed) || new Date(parsed).toISOString().slice(0, 10) !== value) {
    throw new RangeError(`${name} must be a valid YYYY-MM-DD calendar date.`);
  }
  return value;
}

/**
 * Pair hourly PM2.5 observations and one weather metric by actual UTC timestamp.
 * A day contributes only when all 24 expected hourly timestamps fall inside
 * both archives. Means of BOTH variables use the SAME finite paired hours,
 * requiring nonnegative PM concentrations (reported zeros remain valid).
 * Missing values never become zero. Local days use a fixed standard offset,
 * without daylight saving; from/through select inclusive calendar day labels.
 */
export function dailyPairs(pmRecord, heatRecord, options = {}) {
  const {basis = 'local', heatMetric = 'temperature', minHours = 18} = options;
  if (!['local', 'utc'].includes(basis)) throw new RangeError('Calendar basis must be local or utc.');
  if (!Number.isInteger(minHours) || minHours < 1 || minHours > 24) throw new RangeError('Minimum paired hours must be an integer from 1 to 24.');
  const offset = basis === 'utc' ? 0 : options.utcOffsetMinutes ?? pmRecord.standardOffsetMinutes ?? heatRecord.utcOffsetHours * 60;
  if (!finite(offset) || Math.abs(offset) > 14 * 60) throw new RangeError('A valid fixed standard-time offset in minutes is required.');
  const pm = hourlyRecord(pmRecord, options.pmValues ?? pmRecord.values);
  const heat = hourlyRecord(heatRecord, options.heatValues ?? heatRecord.values?.[heatMetric]);
  const from = dateBound(options.from, 'from');
  const through = dateBound(options.through, 'through');
  const first = Math.max(pm.start, heat.start);
  const last = Math.min(pm.end, heat.end);
  const allDays = [];
  const coverage = {completeDays: 0, pmEligibleDays: 0, heatEligibleDays: 0, pairedEligibleDays: 0,
    excludedPairingDays: 0, pmHours: 0, heatHours: 0, pairedHours: 0, eligiblePairedHours: 0,
    expectedHours: 0, minHours, basis, utcOffsetMinutes: offset};
  if (last >= first && (!from || !through || from <= through)) {
    const offsetMs = offset * 60000;
    const firstDay = Math.floor((first + offsetMs) / DAY);
    const lastDay = Math.floor((last + offsetMs) / DAY);
    for (let dayIndex = firstDay; dayIndex <= lastDay; dayIndex++) {
      const date = new Date(dayIndex * DAY).toISOString().slice(0, 10);
      if ((from && date < from) || (through && date > through)) continue;
      const begin = Math.ceil((dayIndex * DAY - offsetMs) / HOUR) * HOUR;
      const end = Math.ceil(((dayIndex + 1) * DAY - offsetMs) / HOUR) * HOUR - HOUR;
      if (begin < first || end > last) continue;
      let pmHours = 0, heatHours = 0, pairedHours = 0, pmSum = 0, heatSum = 0;
      for (let time = begin; time <= end; time += HOUR) {
        const p = pm.values[(time - pm.start) / HOUR];
        const h = heat.values[(time - heat.start) / HOUR];
        const validPm = finite(p) && p >= 0;
        if (validPm) pmHours++;
        if (finite(h)) heatHours++;
        if (validPm && finite(h)) { pairedHours++; pmSum += p; heatSum += h; }
      }
      const eligible = pairedHours >= minHours;
      allDays.push({date, month: Number(date.slice(5, 7)), dayIndex, firstUtc: new Date(begin).toISOString(),
        expectedHours: 24, pmHours, heatHours, pairedHours, eligible,
        pmMean: eligible ? pmSum / pairedHours : null, heatMean: eligible ? heatSum / pairedHours : null});
      coverage.completeDays++;
      coverage.pmEligibleDays += Number(pmHours >= minHours);
      coverage.heatEligibleDays += Number(heatHours >= minHours);
      coverage.pairedEligibleDays += Number(eligible);
      coverage.excludedPairingDays += Number(!eligible);
      coverage.pmHours += pmHours;
      coverage.heatHours += heatHours;
      coverage.pairedHours += pairedHours;
      if (eligible) coverage.eligiblePairedHours += pairedHours;
    }
  }
  coverage.expectedHours = coverage.completeDays * 24;
  return {days: allDays.filter(day => day.eligible), allDays, coverage};
}

/** Pearson correlation, undefined (null) when either variable is constant. */
export function pearson(x, y) {
  if (x.length !== y.length) throw new RangeError('Correlation arrays must have the same length.');
  const pairs = x.map((value, index) => [value, y[index]]).filter(pair => pair.every(finite));
  if (pairs.length < 2) return null;
  const mx = mean(pairs.map(pair => pair[0])), my = mean(pairs.map(pair => pair[1]));
  const dx = pairs.map(pair => pair[0] - mx), dy = pairs.map(pair => pair[1] - my);
  const sx = sumSquares(dx), sy = sumSquares(dy);
  return sx > 0 && sy > 0 ? Math.max(-1, Math.min(1, dot(dx, dy) / Math.sqrt(sx * sy))) : null;
}

function ranks(values) {
  const ordered = values.map((value, index) => ({value, index})).sort((a, b) => a.value - b.value);
  const result = Array(values.length);
  for (let index = 0; index < ordered.length;) {
    let next = index + 1;
    while (next < ordered.length && ordered[next].value === ordered[index].value) next++;
    const rank = (index + next - 1) / 2 + 1;
    for (let tie = index; tie < next; tie++) result[ordered[tie].index] = rank;
    index = next;
  }
  return result;
}

/** Spearman correlation uses average ranks for ties and jointly complete pairs. */
export function spearman(x, y) {
  if (x.length !== y.length) throw new RangeError('Correlation arrays must have the same length.');
  const pairs = x.map((value, index) => [value, y[index]]).filter(pair => pair.every(finite));
  return pearson(ranks(pairs.map(pair => pair[0])), ranks(pairs.map(pair => pair[1])));
}

/** Reorthogonalized QR avoids normal equations and detects deficient designs. */
function leastSquares(columns, y) {
  const n = y.length, p = columns.length, q = [], r = Array.from({length: p}, () => Array(p).fill(0));
  for (let column = 0; column < p; column++) {
    const v = [...columns[column]];
    const originalNorm = Math.sqrt(sumSquares(v));
    for (let pass = 0; pass < 2; pass++) {
      for (let previous = 0; previous < column; previous++) {
        const projection = dot(q[previous], v);
        r[previous][column] += projection;
        for (let index = 0; index < n; index++) v[index] -= projection * q[previous][index];
      }
    }
    const norm = Math.sqrt(sumSquares(v));
    if (norm <= Math.max(1, originalNorm) * 1e-10) return {rank: column};
    r[column][column] = norm;
    q.push(v.map(value => value / norm));
  }
  const beta = q.map(column => dot(column, y));
  for (let row = p - 1; row >= 0; row--) {
    for (let column = row + 1; column < p; column++) beta[row] -= r[row][column] * beta[column];
    beta[row] /= r[row][row];
  }
  const fitted = y.map((_, index) => columns.reduce((sum, column, j) => sum + column[index] * beta[j], 0));
  const leverage = y.map((_, index) => q.reduce((sum, column) => sum + column[index] ** 2, 0));
  return {rank: p, beta, fitted, leverage};
}

function lag1(predictions) {
  const ordered = [...predictions].filter(row => row.date && finite(Date.parse(row.date))).sort((a, b) => a.date.localeCompare(b.date));
  const left = [], right = [];
  for (let index = 1; index < ordered.length; index++) {
    if (Date.parse(ordered[index].date) - Date.parse(ordered[index - 1].date) !== DAY) continue;
    left.push(ordered[index - 1].residual); right.push(ordered[index].residual);
  }
  return {r: pearson(left, right), pairs: left.length};
}

/** Predict raw PM concentration. Month-adjusted fits require an observed month. */
export function predict(result, x, month) {
  if (!result?.available || !finite(x)) return null;
  const c = result.coefficients;
  if (result.model === 'monthAdjusted') {
    return finite(c.monthIntercepts[month]) ? c.monthIntercepts[month] + c.slope * x : null;
  }
  if (result.model === 'quadratic') {
    const z = (x - c.center) / c.scale;
    return c.intercept + c.linear * z + c.quadratic * z * z;
  }
  return c.intercept + c.slope * x;
}

/**
 * Descriptive city-specific fit of daily PM (y) against a thermal metric (x).
 * Linear/quadratic R² is raw-data goodness of fit. Month-adjusted R² is the
 * fraction of WITHIN-MONTH PM variation explained by within-month x changes;
 * totalR2 additionally includes between-month intercept differences.
 * No independent-day p values or confidence intervals are calculated.
 */
export function fitAssociation(days, {model = 'linear'} = {}) {
  if (!['linear', 'quadratic', 'monthAdjusted'].includes(model)) throw new RangeError('Unknown association model.');
  const rows = days.filter(day => finite(day.heatMean) && finite(day.pmMean));
  const x = rows.map(day => day.heatMean), y = rows.map(day => day.pmMean), n = rows.length;
  const months = [...new Set(rows.map(day => day.month ?? Number(day.date?.slice(5, 7))))].sort((a, b) => a - b);
  if (model === 'monthAdjusted' && months.some(month => !Number.isInteger(month) || month < 1 || month > 12)) throw new RangeError('Month-adjusted fits need a valid month for every day.');
  const parameterCount = model === 'quadratic' ? 3 : model === 'monthAdjusted' ? months.length + 1 : 2;
  const result = {available: false, model, n, parameterCount, rank: 0,
    r: pearson(x, y), rho: spearman(x, y), rWithin: null, rhoWithin: null, r2: null, totalR2: null,
    r2Basis: model === 'monthAdjusted' ? 'within-month' : 'total', slope: null, slopePer10: null, intercept: null,
    coefficients: null, predictions: [], lag1: {r: null, pairs: 0}, maxCooksDistance: null};
  if (n <= parameterCount) return {...result, reason: `At least ${parameterCount + 1} paired days are needed for this fit.`};
  const center = mean(x), scale = Math.sqrt(sumSquares(x.map(value => value - center)) / n);
  if (!(scale > Math.max(1, Math.abs(center)) * Number.EPSILON * 32)) return {...result,
    rank: model === 'monthAdjusted' ? months.length : 1, reason: 'The thermal metric is constant; a slope is not defined.'};
  const z = x.map(value => (value - center) / scale);
  const rowMonths = rows.map(day => day.month ?? Number(day.date?.slice(5, 7)));
  const columns = model === 'monthAdjusted' ? months.map(month => rowMonths.map(value => Number(value === month))) : [Array(n).fill(1)];
  columns.push(z);
  if (model === 'quadratic') columns.push(z.map(value => value * value));
  const fit = leastSquares(columns, y);
  if (fit.rank < parameterCount) return {...result, rank: fit.rank, reason: model === 'monthAdjusted'
    ? 'There is no independent within-month thermal variation to estimate a slope.'
    : 'The selected values do not identify all model coefficients.'};
  let coefficients, intercept = null, slope;
  if (model === 'monthAdjusted') {
    slope = fit.beta.at(-1) / scale;
    const monthIntercepts = Object.fromEntries(months.map((month, index) => [month, fit.beta[index] - slope * center]));
    coefficients = {slope, monthIntercepts};
  } else if (model === 'quadratic') {
    coefficients = {center, scale, intercept: fit.beta[0], linear: fit.beta[1], quadratic: fit.beta[2]};
    slope = fit.beta[1] / scale;
  } else {
    slope = fit.beta[1] / scale;
    intercept = fit.beta[0] - slope * center;
    coefficients = {intercept, slope};
  }
  const residuals = y.map((value, index) => value - fit.fitted[index]);
  const sse = sumSquares(residuals), yMean = mean(y), sst = sumSquares(y.map(value => value - yMean));
  let denominator = sst, xDepartures = null, yDepartures = null;
  if (model === 'monthAdjusted') {
    const monthMeans = Object.fromEntries(months.map(month => [month, mean(y.filter((_, index) => rowMonths[index] === month))]));
    const monthXMeans = Object.fromEntries(months.map(month => [month, mean(x.filter((_, index) => rowMonths[index] === month))]));
    xDepartures = x.map((value, index) => value - monthXMeans[rowMonths[index]]);
    yDepartures = y.map((value, index) => value - monthMeans[rowMonths[index]]);
    denominator = sumSquares(yDepartures);
  }
  const mse = sse / (n - parameterCount);
  const exactFit = sse <= Math.max(1, sst) * 1e-24;
  const predictions = rows.map((day, index) => {
    const h = fit.leverage[index];
    const cooksDistance = exactFit ? 0 : h >= 1 - 1e-12 ? null : residuals[index] ** 2 / (parameterCount * mse) * h / (1 - h) ** 2;
    return {date: day.date, month: rowMonths[index], x: x[index], y: y[index], fitted: fit.fitted[index],
      residual: residuals[index], leverage: h, cooksDistance,
      ...(xDepartures ? {xDeparture: xDepartures[index], yDeparture: yDepartures[index], fittedDeparture: slope * xDepartures[index]} : {})};
  });
  const distances = predictions.map(row => row.cooksDistance).filter(finite);
  return {...result, available: true, reason: null, rank: fit.rank, coefficients, intercept, slope, slopePer10: slope * 10,
    slopeAt: model === 'quadratic' ? center : null, r2: denominator > 0 ? 1 - sse / denominator : null,
    rWithin: xDepartures ? pearson(xDepartures, yDepartures) : null,
    rhoWithin: xDepartures ? spearman(xDepartures, yDepartures) : null,
    totalR2: sst > 0 ? 1 - sse / sst : null, residualSumSquares: sse, residualDf: n - parameterCount,
    predictions, lag1: lag1(predictions), maxCooksDistance: distances.length ? Math.max(...distances) : null};
}
