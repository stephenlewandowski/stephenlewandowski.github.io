/** Observed hourly co-occurrence. Thresholds are descriptive references, not hourly regulatory standards. */
const HOUR = 3600000;
const START_2024 = Date.UTC(2024, 0, 1);
const finite = Number.isFinite;
const seasons = {DJF: [12, 1, 2], MAM: [3, 4, 5], JJA: [6, 7, 8], SON: [9, 10, 11]};

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
 * Join real reported UTC timestamps, retaining shared finite thermal and
 * nonnegative PM values. PM >= pmThreshold and thermal >= heatThreshold
 * (above) or <= heatThreshold (below) are inclusive. Missing is never zero.
 *
 * expectedHours counts selected labels in the overlapping source extents.
 * Unlike dailyPairs, partial endpoint calendar days ARE counted and reported.
 * A run is consecutive selected hourly labels satisfying both conditions;
 * midnight alone does not split a run. Missing, unselected and observed-false
 * labels split runs. Duration is a count of labelled samples, not verified
 * physical overlap of source sampling intervals or a personal exposure dose.
 * Censor reasons identify unknown continuation across a missing label,
 * selection boundary or archive boundary. An observed-false neighbour is null.
 */
export function hourlyJoint(pmRecord, heatRecord, options = {}) {
  const {basis = 'local', heatMetric = 'temperature', pmThreshold = 35, heatThreshold = 30,
    direction = 'above', season = 'all'} = options;
  if (!['local', 'utc'].includes(basis)) throw new RangeError('Calendar basis must be local or utc.');
  if (!['above', 'below'].includes(direction)) throw new RangeError('Thermal direction must be above or below.');
  if (season !== 'all' && !Object.hasOwn(seasons, season)) throw new RangeError('Season must be all, DJF, MAM, JJA or SON.');
  if (!finite(pmThreshold) || pmThreshold < 0 || !finite(heatThreshold)) throw new RangeError('Finite reference thresholds and a nonnegative PM threshold are required.');
  const offset = basis === 'utc' ? 0 : options.utcOffsetMinutes ?? pmRecord.standardOffsetMinutes ?? heatRecord.utcOffsetHours * 60;
  if (!finite(offset) || Math.abs(offset) > 14 * 60) throw new RangeError('A valid fixed standard-time offset in minutes is required.');
  const from = dateBound(options.from, 'from'), through = dateBound(options.through, 'through');
  if (from && through && from > through) throw new RangeError('from must not be later than through.');
  const pm = hourlyRecord(pmRecord, options.pmValues ?? pmRecord.values);
  const heat = hourlyRecord(heatRecord, options.heatValues ?? heatRecord.values?.[heatMetric]);
  const first = Math.max(pm.start, heat.start), last = Math.min(pm.end, heat.end);
  const offsetMs = offset * 60000;
  const dateTime = time => new Date(time + offsetMs).toISOString();
  const selected = time => {
    const label = dateTime(time), date = label.slice(0, 10), month = Number(label.slice(5, 7));
    return (!from || date >= from) && (!through || date <= through) && (season === 'all' || seasons[season].includes(month));
  };
  const status = time => {
    if (time < first || time > last) return 'record';
    if (!selected(time)) return 'selection';
    const p = pm.values[(time - pm.start) / HOUR], h = heat.values[(time - heat.start) / HOUR];
    if (!finite(p) || p < 0 || !finite(h)) return 'missing';
    return p >= pmThreshold && (direction === 'above' ? h >= heatThreshold : h <= heatThreshold) ? 'both' : 'false';
  };
  const totals = {expectedHours: 0, pairedHours: 0, missingHours: 0, pmValidHours: 0, heatValidHours: 0,
    pmHoursAbove: 0, thermalHoursMeeting: 0, bothHours: 0};
  const months = new Map(), dates = new Map(), events = [];
  let run = null, firstSelected = null, lastSelected = null;
  const endRun = nextStatus => {
    if (!run) return;
    run.rightCensorReason = nextStatus === 'false' ? null : nextStatus;
    run.rightCensored = run.rightCensorReason !== null;
    run.censored = run.leftCensored || run.rightCensored;
    events.push(run);
    run = null;
  };
  for (let time = first; time <= last; time += HOUR) {
    if (!selected(time)) {endRun('selection'); continue;}
    firstSelected ??= time;
    lastSelected = time;
    const label = dateTime(time), date = label.slice(0, 10), month = label.slice(0, 7);
    if (!months.has(month)) months.set(month, {month, expectedHours: 0, pairedHours: 0, missingHours: 0,
      pmHoursAbove: 0, thermalHoursMeeting: 0, bothHours: 0, daysWithBoth: 0});
    if (!dates.has(date)) dates.set(date, {date, expectedHours: 0, pairedHours: 0, bothHours: 0});
    const monthly = months.get(month), daily = dates.get(date);
    totals.expectedHours++; monthly.expectedHours++; daily.expectedHours++;
    const p = pm.values[(time - pm.start) / HOUR], h = heat.values[(time - heat.start) / HOUR];
    const validPm = finite(p) && p >= 0, validHeat = finite(h);
    totals.pmValidHours += Number(validPm); totals.heatValidHours += Number(validHeat);
    if (!validPm || !validHeat) {
      totals.missingHours++; monthly.missingHours++; endRun('missing'); continue;
    }
    totals.pairedHours++; monthly.pairedHours++; daily.pairedHours++;
    const highPm = p >= pmThreshold, thermal = direction === 'above' ? h >= heatThreshold : h <= heatThreshold;
    totals.pmHoursAbove += Number(highPm); monthly.pmHoursAbove += Number(highPm);
    totals.thermalHoursMeeting += Number(thermal); monthly.thermalHoursMeeting += Number(thermal);
    if (!highPm || !thermal) {endRun('false'); continue;}
    totals.bothHours++; monthly.bothHours++; daily.bothHours++;
    const local = label.slice(0, 16).replace('T', ' '), utc = new Date(time).toISOString();
    if (!run) {
      const previous = status(time - HOUR), reason = previous === 'false' ? null : previous;
      run = {startUtc: utc, endUtc: utc, startLocal: local, endLocal: local,
        startLabel: local, endLabel: local, durationHours: 0, leftCensorReason: reason,
        leftCensored: reason !== null};
    }
    run.endUtc = utc; run.endLocal = local; run.endLabel = local; run.durationHours++;
  }
  endRun(status(last + HOUR));
  const days = [...dates.values()];
  for (const day of days) {
    day.partialBoundary = day.expectedHours < 24;
    if (day.bothHours) months.get(day.date.slice(0, 7)).daysWithBoth++;
  }
  const finish = row => ({...row, fractionOfPaired: row.pairedHours ? row.bothHours / row.pairedHours : null,
    pmOnlyHours: row.pmHoursAbove - row.bothHours,
    thermalOnlyHours: row.thermalHoursMeeting - row.bothHours,
    neitherHours: row.pairedHours - row.pmHoursAbove - row.thermalHoursMeeting + row.bothHours});
  const bins = [
    {label: '1', min: 1, max: 1}, {label: '2–3', min: 2, max: 3}, {label: '4–7', min: 4, max: 7},
    {label: '8–11', min: 8, max: 11}, {label: '12–23', min: 12, max: 23}, {label: '24+', min: 24, max: null}
  ];
  const runHistogram = bins.map(bin => {
    const matches = events.filter(event => event.durationHours >= bin.min && (bin.max === null || event.durationHours <= bin.max));
    return {...bin, events: matches.length, count: matches.length, hours: matches.reduce((sum, event) => sum + event.durationHours, 0),
      censoredEvents: matches.filter(event => event.censored).length};
  });
  return {...finish(totals), daysWithBoth: days.filter(day => day.bothHours > 0).length,
    longestRunHours: events.reduce((longest, event) => Math.max(longest, event.durationHours), 0),
    eventCount: events.length, censoredEventCount: events.filter(event => event.censored).length,
    events, months: [...months.values()].map(finish), days, runHistogram,
    partialBoundaryDays: days.filter(day => day.partialBoundary),
    basis, utcOffsetMinutes: offset, heatMetric, season, from, through,
    thresholds: {pm: pmThreshold, heat: heatThreshold, direction, inclusive: true},
    coverageStartUtc: firstSelected === null ? null : new Date(firstSelected).toISOString(),
    coverageEndUtc: lastSelected === null ? null : new Date(lastSelected).toISOString(),
    durationMeaning: 'Consecutive reported hourly sample labels; unverified physical sampling-interval alignment.'};
}
