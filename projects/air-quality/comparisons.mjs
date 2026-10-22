import {summarize} from './analysis.mjs?v=20261023';
import {pm25Benchmark, thresholdCounts, PM25_STANDARDS, standardOffset} from './benchmarks.mjs?v=20261023';

const $ = selector => document.querySelector(selector);
const NS = 'http://www.w3.org/2000/svg';
const benchmarkCache = new WeakMap();
const countsCache = new WeakMap();
const fmt = (value, digits = 1) => Number.isFinite(value) ? value.toLocaleString('en', {minimumFractionDigits: digits, maximumFractionDigits: digits}) : '—';
const name = record => record.label || record.city;
const monthName = month => new Intl.DateTimeFormat('en', {month: 'short', timeZone: 'UTC'}).format(Date.UTC(2024, month, 1));
const el = (tag, text, attributes = {}) => {
  const node = document.createElement(tag);
  if (text !== null) node.textContent = text;
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
};
const svg = (tag, attributes = {}, text = '') => {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  node.textContent = text;
  return node;
};
const rowName = record => {
  const cell = el('th', null, {scope: 'row'});
  cell.append(el('span', '', {class: 'air-swatch', style: `--series:${record.color}`}), document.createTextNode(name(record)));
  return cell;
};
const noteCell = (text, note, className = '') => {
  const cell = el('td', text, {class: className});
  cell.append(el('span', note, {class: 'capture'}));
  return cell;
};
const countLabel = count => `${count.above.toLocaleString()} / ${count.valid.toLocaleString()} (${fmt(count.percent)}%)`;

function benchmark(record) {
  if (!benchmarkCache.has(record)) benchmarkCache.set(record, pm25Benchmark(record));
  return benchmarkCache.get(record);
}

function counts(record, options) {
  const key = `${options.threshold}:${options.first}:${options.last}:${options.basis}`;
  const previous = countsCache.get(record);
  if (previous?.key === key) return previous.value;
  const value = thresholdCounts(record, options.threshold, options);
  countsCache.set(record, {key, value});
  return value;
}

function renderStandards(records) {
  const body = $('#standards tbody');
  body.replaceChildren();
  const notes = [];
  for (const record of records) {
    if (record.quality?.regulatoryComparisonExcluded) {
      const row = el('tr', null); row.append(rowName(record));
      for (let column = 0; column < 5; column++) row.append(noteCell('Not compared', 'Provider requests exclusion from NAAQS comparison'));
      body.append(row); notes.push(`${name(record)}, ${record.year}: POC 3 is omitted from this reference table under the provider's exclusion request; measured values remain available in the explorer.`); continue;
    }
    const data = benchmark(record);
    const annualNote = data.annualMean === null ? 'Insufficient data' : data.annualMean > PM25_STANDARDS.annualSecondary ? 'Above 9.0 and 15.0 reference levels' : data.annualMean > PM25_STANDARDS.annualPrimary ? 'Above 9.0; below 15.0 reference level' : data.annualMean === PM25_STANDARDS.annualPrimary ? 'At 9.0 reference level' : 'Below 9.0 and 15.0 reference levels';
    const dailyNote = data.p98 === null ? 'Insufficient data' : `${data.p98 > 35 ? 'Above' : data.p98 === 35 ? 'At' : 'Below'} 35 reference level · rank ${data.p98Rank}`;
    const capture = Math.min(...data.quarters.map(quarter => quarter.capturePercent));
    const row = el('tr', null);
    const label = rowName(record);
    label.append(el('span', record.networkMean ? 'Network mean · context only' : 'Individual monitoring location', {class: 'capture'}));
    row.append(label, noteCell(fmt(data.annualMean, 2), annualNote), noteCell(fmt(data.p98), dailyNote),
      noteCell(`${data.daysAbove35} / ${data.validDays}`, 'EPA-precision daily values'),
      noteCell(`${fmt(capture)}%`, capture >= 75 ? 'All quarters ≥75%' : 'At least one quarter below 75%', capture < 75 ? 'air-low-capture' : ''));
    body.append(row);
    notes.push(`${name(record)}: ${data.validDays}/${data.expectedDays} valid local days${data.highValueExceptionDays ? `, including ${data.highValueExceptionDays} sparse high day${data.highValueExceptionDays === 1 ? '' : 's'} using the conservative lower bound` : ''}.`);
  }
  $('#standards-note').textContent = notes.length ? notes.join(' ') + ' No exceptional-event exclusions or regulatory data-substitution tests are applied.' : 'Select a record above to compare its selected-year statistics.';
}

function plotFrame(id, {maximum = 100, unit = '% of valid days', xLabel = ''} = {}) {
  const chart = $(id);
  const width = Math.max(300, chart.clientWidth || 1120);
  const height = width < 600 ? 290 : 330;
  const left = width < 600 ? 44 : 64;
  const right = width - 22;
  const top = 30;
  const bottom = height - (xLabel ? 58 : 40);
  chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
  chart.querySelectorAll('g').forEach(node => node.remove());
  const g = svg('g');
  chart.append(g);
  const y = value => bottom - value / maximum * (bottom - top);
  const step = maximum / 5;
  for (let tick = 0; tick <= 5; tick++) {
    const value = step * tick;
    g.append(svg('line', {x1: left, x2: right, y1: y(value), y2: y(value), stroke: '#e2e6e4'}));
    g.append(svg('text', {x: left - 9, y: y(value) + 4, 'text-anchor': 'end'}, String(Math.round(value))));
  }
  g.append(svg('text', {x: left, y: 17, class: 'axis-label'}, unit));
  if (xLabel) g.append(svg('text', {x: (left + right) / 2, y: height - 8, 'text-anchor': 'middle', class: 'axis-label'}, xLabel));
  return {chart, g, width, height, left, right, top, bottom, y};
}

function monthCounts(data, threshold) {
  return Array.from({length: 12}, (_, index) => {
    const days = data.dailyValues.filter(day => day.month === index + 1 && day.valid);
    const above = days.filter(day => day.mean > threshold).length;
    return {above, valid: days.length, percent: days.length ? 100 * above / days.length : null};
  });
}

function renderMonths(series, options) {
  const frame = plotFrame('#frequency-chart');
  const {g, width, left, right, bottom, y} = frame;
  const slot = (right - left) / 12;
  const barWidth = Math.min(22, slot * .78 / Math.max(1, series.length));
  const head = el('tr', null);
  head.append(el('th', 'Month', {scope: 'col'}));
  for (const {record} of series) head.append(el('th', name(record), {scope: 'col'}));
  $('#monthly-counts thead').replaceChildren(head);
  const body = $('#monthly-counts tbody');
  body.replaceChildren();
  const data = series.map(item => ({...item, months: monthCounts(item.data, options.threshold)}));
  for (let month = 0; month < 12; month++) {
    if (width >= 600 || month % 2 === 0) g.append(svg('text', {x: left + slot * (month + .5), y: bottom + 22, 'text-anchor': 'middle'}, monthName(month)));
    const row = el('tr', null);
    row.append(el('th', monthName(month), {scope: 'row'}));
    data.forEach(({record, months}, index) => {
      const count = months[month];
      row.append(el('td', count.valid ? countLabel(count) : '— (no valid days)'));
      if (count.percent === null) return;
      const rect = svg('rect', {x: left + slot * (month + .5) + (index - data.length / 2) * barWidth,
        y: y(count.percent), width: barWidth - 1, height: bottom - y(count.percent), fill: record.color});
      rect.append(svg('title', {}, `${name(record)}, ${monthName(month)}: ${countLabel(count)}`));
      g.append(rect);
    });
    body.append(row);
  }
  $('#monthly-threshold-note').textContent = `Percentage of valid calendar days with a mean above ${fmt(options.threshold)} µg/m³, using ${options.basis === 'utc' ? 'UTC days' : 'local standard-time days'}. Bars use the selected dates. Colors match the records above; months without valid days have no bar.`;
}

function renderDistribution(series, options) {
  const distribution = series.map(({record, data}) => ({record, values: options.distributionMode === 'daily'
    ? data.dailyValues.filter(day => day.valid).map(day => day.mean)
    : record.values.slice(options.first, options.last + 1).filter((value, index) => {
      if (!Number.isFinite(value)) return false;
      if (options.basis !== 'local-standard') return true;
      // Match the local-calendar-year restriction used by thresholdCounts.
      const offset = standardOffset(record) / 60;
      return new Date(Date.parse(record.startUtc) + (options.first + index + offset) * 3600000).getUTCFullYear() === record.year;
    })}));
  const maximum = Math.max(10, ...distribution.map(item => summarize(item.values).max || 0));
  const ceiling = Math.ceil(maximum / 10) * 10;
  const {g, left, right, bottom, y} = plotFrame('#distribution-chart', {maximum: ceiling, unit: 'PM₂.₅ · µg/m³', xLabel: '% of valid values strictly above the concentration'});
  const x = percent => left + percent / 100 * (right - left);
  for (const tick of [0, 20, 40, 60, 80, 100]) g.append(svg('text', {x: x(tick), y: bottom + 22, 'text-anchor': 'middle'}, String(tick)));
  if (options.threshold <= ceiling) {
    g.append(svg('line', {x1: left, x2: right, y1: y(options.threshold), y2: y(options.threshold), class: 'air-threshold-line'}));
    g.append(svg('text', {x: right - 3, y: y(options.threshold) - 6, 'text-anchor': 'end', class: 'air-threshold-label'}, `Chosen threshold: ${fmt(options.threshold)}`));
  }
  const body = $('#percentiles tbody');
  body.replaceChildren();
  for (const {record, values} of distribution) {
    const sorted = values.toSorted((a, b) => b - a);
    let path = '';
    let lastValue = null;
    let lastAdded = -1;
    for (let index = 0; index < sorted.length; index++) {
      if (sorted[index] === lastValue) continue;
      lastValue = sorted[index];
      // Limit SVG size, while preserving the ends and the strict-above rank of ties.
      if (index > 0 && index < sorted.length - 1 && index - lastAdded < sorted.length / 600) continue;
      path += `${path ? 'L' : 'M'}${x(index / sorted.length * 100).toFixed(2)},${y(sorted[index]).toFixed(2)}`;
      lastAdded = index;
    }
    g.append(svg('path', {d: path, fill: 'none', stroke: record.color, 'stroke-width': 2.3, 'aria-label': name(record)}));
    const stats = summarize(values);
    const row = el('tr', null);
    row.append(rowName(record), el('td', String(stats.count)), el('td', fmt(stats.median)), el('td', fmt(stats.p95)), el('td', fmt(stats.max)));
    body.append(row);
  }
  $('#distribution-note').textContent = `Each curve orders the ${options.distributionMode === 'daily' ? 'valid calendar-day means' : 'valid hourly measurements'} from highest to lowest. For example, the height near 5% shows a concentration exceeded by about 5% of valid values. This view uses the selected dates${options.distributionMode === 'daily' ? ' and day basis' : ''}; missing values are excluded.`;
}

export function renderComparisons(records, options) {
  renderStandards(records);
  for (const selector of ['#frequency-legend', '#distribution-legend']) {
    const legend = $(selector);
    legend.replaceChildren();
    for (const record of records) {
      const entry = el('span', null);
      entry.append(el('span', '', {class: 'air-swatch', style: `--series:${record.color}`}), document.createTextNode(name(record)));
      legend.append(entry);
    }
  }
  const series = records.map(record => ({record, data: counts(record, options)}));
  const body = $('#counts tbody');
  body.replaceChildren();
  for (const {record, data} of series) {
    const row = el('tr', null);
    row.append(rowName(record));
    for (const key of ['hourly', 'daily', 'rolling8', 'rolling24']) row.append(noteCell(data[key].valid ? countLabel(data[key]) : '— (no valid values)', `${data[key].expected.toLocaleString()} possible`));
    row.append(el('td', `${data.hourly.longestRun.toLocaleString()} h`));
    body.append(row);
  }
  const first = new Date(Date.UTC(options.year ?? 2024, 0, 1) + options.first * 3600000).toISOString().slice(0, 10);
  const last = new Date(Date.UTC(options.year ?? 2024, 0, 1) + options.last * 3600000).toISOString().slice(0, 10);
  $('#count-period').textContent = `${first} through ${last} (UTC selection) · above ${fmt(options.threshold)} µg/m³ · ${options.basis === 'utc' ? 'UTC days' : 'local standard-time days'}`;
  $('#download-comparison').disabled = !records.length;
  renderMonths(series, options);
  renderDistribution(series, options);
}

export function comparisonCsv(records, options) {
  const rows = [['record', 'scope', 'pollutant', 'units', 'period', 'day_basis', 'metric', 'value', 'valid_denominator', 'possible_denominator', 'threshold_ug_m3']];
  const period = `${new Date(Date.UTC(options.year ?? 2024, 0, 1) + options.first * 3600000).toISOString().slice(0, 10)}/${new Date(Date.UTC(options.year ?? 2024, 0, 1) + options.last * 3600000).toISOString().slice(0, 10)}`;
  for (const record of records) {
    const scope = record.networkMean ? 'network mean; context only' : record.station.name;
    const prefix = [name(record), scope, 'PM2.5', 'ug/m3'];
    const data = counts(record, options);
    for (const key of ['hourly', 'daily', 'rolling8', 'rolling24']) {
      rows.push([...prefix, period, options.basis, `${key}_strictly_above`, data[key].above, data[key].valid, data[key].expected, options.threshold]);
    }
    rows.push([...prefix, period, options.basis, 'longest_consecutive_hours_above', data.hourly.longestRun, '', '', options.threshold]);
    if (record.quality?.regulatoryComparisonExcluded) {
      rows.push([...prefix, `${record.year} full local year`, 'local-standard', 'regulatory_comparison_excluded', 'true', '', '', '']);
      monthCounts(data, options.threshold).forEach((count, index) => rows.push([...prefix, `${period}; month ${index + 1}`, options.basis, 'daily_strictly_above', count.above, count.valid, '', options.threshold]));
      continue;
    }
    const full = benchmark(record);
    for (const [metric, value, threshold] of [['annual_component', full.annualMean, 9], ['daily_p98_component', full.p98, 35], ['epa_precision_days_above_35', full.daysAbove35, 35], ['sparse_high_days', full.highValueExceptionDays, '']]) {
      rows.push([...prefix, `${record.year} full local year; one-year comparison only`, 'local-standard; EPA tenths truncation', metric, value ?? '', full.validDays, full.expectedDays, threshold]);
    }
    for (const quarter of full.quarters) rows.push([...prefix, `${record.year} Q${quarter.quarter}`, 'local-standard; EPA tenths truncation', 'valid_days', quarter.validDays, quarter.expectedDays, quarter.expectedDays, '']);
    monthCounts(data, options.threshold).forEach((count, index) => rows.push([...prefix, `${period}; month ${index + 1}`, options.basis, 'daily_strictly_above', count.above, count.valid, '', options.threshold]));
  }
  return rows.map(row => row.map(value => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\r\n') + '\r\n';
}
