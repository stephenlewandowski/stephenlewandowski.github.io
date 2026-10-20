import {HOURS_2024, START_2024, aggregate, summarize, monthlySummary} from './analysis.mjs';
import {renderComparisons, comparisonCsv} from './comparisons.mjs';

const $ = selector => document.querySelector(selector);
const NS = 'http://www.w3.org/2000/svg';
const colors = {seoul: '#16766a', london: '#3463ad', beijing: '#a94f30'};
const number = value => value === null || !Number.isFinite(value) ? '—' : value.toLocaleString('en', {maximumFractionDigits: 1, minimumFractionDigits: 1});
const dateLabel = (hour, options = {}) => new Intl.DateTimeFormat('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC', ...options}).format(START_2024 + hour * 3600000);
const isoDate = hour => new Date(START_2024 + hour * 3600000).toISOString().slice(0, 10);
const element = (tag, text, attributes = {}) => {
  const node = document.createElement(tag);
  if (text !== null) node.textContent = text;
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
};
const svgNode = (tag, attributes = {}, text = '') => {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  node.textContent = text;
  return node;
};
const swatch = color => element('span', '', {class: 'air-swatch', style: `--series:${color}`});
const state = {records: [], selected: new Set(), mode: 'daily', first: 0, last: HOURS_2024 - 1, threshold: 35, basis: 'utc', distributionMode: 'hourly'};
const box = {left: 66, right: 1090, top: 28, bottom: 344};
let plot = null;
let dragStart = null;

function validateRecord(record) {
  if (record.year !== 2024 || record.intervalMinutes !== 60 || record.values.length !== HOURS_2024) throw new Error(`Unexpected time grid for ${record.city}`);
  if (!record.values.every(value => value === null || Number.isFinite(value) && value >= 0)) throw new Error(`Invalid concentration in ${record.city}`);
  record.color = colors[record.id] || '#654d82';
  record.offset = (Date.parse(record.startUtc) - START_2024) / 3600000;
  record.aggregates = Object.fromEntries(['hourly', 'daily', 'rolling8', 'rolling24'].map(mode => [mode, aggregate(record.values, mode)]));
  record.months = monthlySummary(record.values);
  return record;
}

function selectedRecords() { return state.records.filter(record => state.selected.has(record.id)); }

function setRange(first, last) {
  state.first = Math.max(0, Math.min(HOURS_2024 - 24, Math.floor(first / 24) * 24));
  state.last = Math.max(state.first + 23, Math.min(HOURS_2024 - 1, Math.floor(last / 24) * 24 + 23));
  $('#from').value = isoDate(state.first);
  $('#through').value = isoDate(state.last);
  render();
}

function drawChart(records) {
  const chart = $('#chart');
  const width = Math.max(300, chart.clientWidth || 1120);
  const height = width < 600 ? 300 : 400;
  box.left = width < 600 ? 42 : 66;
  box.right = width - 20;
  box.bottom = height - 50;
  chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
  chart.querySelectorAll('g,defs').forEach(node => node.remove());
  const group = svgNode('g');
  chart.append(group);
  const allPoints = records.map(record => ({record, points: record.aggregates[state.mode].filter(point => point.hour >= state.first && point.hour <= state.last)}));
  let maximum = 0;
  for (const {points} of allPoints) for (const point of points) if (point.value !== null) maximum = Math.max(maximum, point.value);
  const step = maximum > 500 ? 100 : maximum > 200 ? 50 : maximum > 80 ? 20 : maximum > 30 ? 10 : 5;
  const ceiling = Math.max(step, Math.ceil(maximum / step) * step);
  const span = Math.max(24, state.last - state.first + 1);
  const x = hour => box.left + (hour - state.first) / span * (box.right - box.left);
  const y = value => box.bottom - value / ceiling * (box.bottom - box.top);
  for (let tick = 0; tick <= ceiling; tick += step) {
    group.append(svgNode('line', {x1: box.left, x2: box.right, y1: y(tick), y2: y(tick), stroke: '#e2e6e4'}));
    group.append(svgNode('text', {x: box.left - 12, y: y(tick) + 4, 'text-anchor': 'end'}, String(tick)));
  }
  group.append(svgNode('text', {x: box.left, y: 17, class: 'axis-label'}, 'PM₂.₅ · µg/m³'));
  if (state.threshold <= ceiling) {
    group.append(svgNode('line', {x1: box.left, x2: box.right, y1: y(state.threshold), y2: y(state.threshold), class: 'air-threshold-line'}));
    group.append(svgNode('text', {x: box.right - 4, y: y(state.threshold) - 6, 'text-anchor': 'end', class: 'air-threshold-label'}, `Chosen threshold: ${number(state.threshold)}`));
  }
  if (span > 24 * 90) {
    for (let month = 0; month < 12; month += width < 600 ? 2 : 1) {
      const hour = (Date.UTC(2024, month, 1) - START_2024) / 3600000;
      if (hour >= state.first && hour <= state.last) group.append(svgNode('text', {x: x(hour), y: height - 20, 'text-anchor': 'start'}, dateLabel(hour, {day: undefined})));
    }
  } else {
    const ticks = width < 600 ? 3 : 5;
    for (let i = 0; i <= ticks; i++) {
      const hour = state.first + (span - 1) * i / ticks;
      group.append(svgNode('text', {x: x(hour), y: height - 20, 'text-anchor': i === 0 ? 'start' : i === ticks ? 'end' : 'middle'}, dateLabel(hour)));
    }
  }
  for (const {record, points} of allPoints) {
    let path = '';
    let open = false;
    for (const point of points) {
      if (point.value === null) { open = false; continue; }
      const offset = state.mode === 'daily' ? 0 : record.offset;
      path += `${open ? 'L' : 'M'}${x(point.hour + offset).toFixed(2)},${y(point.value).toFixed(2)}`;
      open = true;
    }
    const line = svgNode('path', {d: path, fill: 'none', stroke: record.color, 'stroke-width': record.id === 'seoul' ? 2.4 : 1.8, 'stroke-linejoin': 'round', 'aria-label': record.city});
    group.append(line);
  }
  const cursor = svgNode('line', {x1: 0, x2: 0, y1: box.top, y2: box.bottom, stroke: '#17324d', 'stroke-dasharray': '3 4', visibility: 'hidden'});
  const brush = svgNode('rect', {x: 0, y: box.top, width: 0, height: box.bottom - box.top, fill: '#17324d', opacity: .1});
  group.append(brush, cursor);
  plot = {x, span, cursor, brush, records, width};
  chart.setAttribute('aria-label', `PM₂.₅ from ${dateLabel(state.first)} through ${dateLabel(state.last)} 2024, ${$('#average').selectedOptions[0].textContent}`);
}

function tables(records) {
  const body = $('#summary tbody');
  body.replaceChildren();
  const expected = state.last - state.first + 1;
  for (const record of records) {
    const values = record.values.slice(state.first, state.last + 1);
    const stats = summarize(values);
    const row = element('tr', null);
    const name = element('th', null, {scope: 'row'});
    name.append(swatch(record.color), document.createTextNode(record.label || record.city));
    row.append(name, element('td', `${stats.count.toLocaleString()} / ${expected.toLocaleString()} (${(100 * stats.count / expected).toFixed(1)}%)`));
    for (const key of ['mean', 'median', 'p95', 'max']) row.append(element('td', number(stats[key])));
    body.append(row);
  }
  const header = element('tr', null);
  header.append(element('th', 'Month', {scope: 'col'}));
  for (const record of records) header.append(element('th', record.label || record.city, {scope: 'col'}));
  $('#monthly thead').replaceChildren(header);
  const monthlyBody = $('#monthly tbody');
  monthlyBody.replaceChildren();
  for (let month = 0; month < 12; month++) {
    const row = element('tr', null);
    row.append(element('th', new Intl.DateTimeFormat('en', {month: 'long', timeZone: 'UTC'}).format(Date.UTC(2024, month, 1)), {scope: 'row'}));
    for (const record of records) {
      const data = record.months[month];
      const cell = element('td', number(data.mean));
      cell.append(element('span', `${(data.count / data.expected * 100).toFixed(1)}% of hours`, {class: 'capture'}));
      row.append(cell);
    }
    monthlyBody.append(row);
  }
}

function render() {
  const records = selectedRecords();
  $('#chart-tooltip').hidden = true;
  drawChart(records);
  tables(records);
  renderComparisons(records, state);
  $('#selection-note').textContent = records.length ? `${dateLabel(state.first)}–${dateLabel(state.last)} 2024 · ${records.map(record => record.label || record.city).join(', ')} · UTC` : 'Select at least one record to draw the chart.';
  $('#download').disabled = !records.length;
  $('#chart-note').textContent = state.mode === 'hourly'
    ? 'Hourly values preserve individual events. The vertical axis adjusts to the selected records and dates; compare the axis labels when changing the view.'
    : `${$('#average').selectedOptions[0].textContent}: at least 75% of the hours must be present. Gaps are not filled. The vertical axis adjusts to the selected records and dates.`;
  $('#chart-note').textContent += ` The dashed line uses the chosen concentration threshold (${number(state.threshold)} µg/m³), when within the plotted range. It is not a regulatory limit for the displayed averaging window.`;
}

function pointerHour(event) {
  const rect = $('#chart').getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width * plot.width;
  return Math.max(state.first, Math.min(state.last, state.first + (x - box.left) / (box.right - box.left) * plot.span));
}

function inspect(event) {
  if (!plot || !plot.records.length) return;
  const hour = pointerHour(event);
  const x = plot.x(hour);
  plot.cursor.setAttribute('x1', x);
  plot.cursor.setAttribute('x2', x);
  plot.cursor.setAttribute('visibility', 'visible');
  if (dragStart !== null) {
    plot.brush.setAttribute('x', plot.x(Math.min(hour, dragStart)));
    plot.brush.setAttribute('width', Math.abs(x - plot.x(dragStart)));
  }
  const tooltip = $('#chart-tooltip');
  const displayHour = state.mode === 'daily' ? Math.floor(hour / 24) * 24 : Math.round(hour);
  tooltip.replaceChildren(element('strong', state.mode === 'daily' ? `${dateLabel(displayHour)} 2024 · UTC day` : `${dateLabel(displayHour)} 2024 · UTC`));
  for (const record of plot.records) {
    const points = record.aggregates[state.mode];
    const index = state.mode === 'daily' ? Math.floor(hour / 24) : Math.max(0, Math.min(points.length - 1, Math.round(hour - record.offset)));
    const point = points[index];
    const time = state.mode === 'daily' ? '' : ` · ${new Date(START_2024 + (point.hour + record.offset) * 3600000).toISOString().slice(11, 16)}`;
    const row = element('div', null);
    row.append(swatch(record.color), document.createTextNode(`${record.label || record.city}: ${number(point.value)}${point.value === null ? '' : ' µg/m³'}${time}`));
    tooltip.append(row);
  }
  tooltip.hidden = false;
}

function downloadText(text, filename) {
  const url = URL.createObjectURL(new Blob([text], {type: 'text/csv;charset=utf-8'}));
  const link = element('a', '', {href: url, download: filename});
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportCsv() {
  const lines = ['timestamp_utc,city,record_id,pm25_ug_m3,monitors_reporting'];
  for (const record of selectedRecords()) {
    for (let hour = state.first; hour <= state.last; hour++) {
      const timestamp = new Date(START_2024 + (hour + record.offset) * 3600000).toISOString();
      lines.push([timestamp, record.city, record.station.id, record.values[hour] ?? '', record.stationCounts?.[hour] ?? ''].join(','));
    }
  }
  downloadText(lines.join('\r\n') + '\r\n', `pm25-${isoDate(state.first)}-to-${isoDate(state.last)}.csv`);
}

function sourceCards(records, manifest) {
  const container = $('#sources');
  container.replaceChildren();
  for (const record of records) {
    const article = element('article', null);
    article.append(element('h4', `${record.city} · ${record.station.name}`));
    article.append(element('p', record.station.aggregation || `${record.station.type}. Provider: ${record.station.provider}.`));
    const capture = summarize(record.values).count / HOURS_2024 * 100;
    article.append(element('p', `${capture.toFixed(2)}% of the 2024 UTC hourly grid has values. All four seasons meet the 75% capture threshold used for inclusion.`));
    const status = record.quality?.qaStatus || (record.quality?.ratificationStatus
      ? 'The archive does not supply a ratification status for these readings.' : null);
    if (status) article.append(element('p', status));
    const listing = manifest.records.find(item => item.id === record.id);
    const links = element('p', null);
    const sourceUrl = record.station.url || record.sources?.[0]?.url || listing.sourceUrl;
    if (sourceUrl) links.append(element('a', 'Original source', {href: sourceUrl}), document.createTextNode(' · '));
    links.append(element('a', 'Hourly data and provenance (JSON)', {href: record.dataFile || listing.file}));
    article.append(links);
    container.append(article);
  }
}

async function start() {
  const response = await fetch('data/manifest.json');
  if (!response.ok) throw new Error('The data manifest could not be loaded.');
  const manifest = await response.json();
  state.records = await Promise.all(manifest.records.map(async item => {
    const result = await fetch(item.file);
    if (!result.ok) throw new Error(`The ${item.id} record could not be loaded.`);
    return validateRecord(await result.json());
  }));
  const seoulResponse = await fetch('data/seoul-stations-2024.json');
  if (!seoulResponse.ok) throw new Error('The Seoul district measurements could not be loaded.');
  const seoulData = await seoulResponse.json();
  if (seoulData.year !== 2024 || seoulData.intervalMinutes !== 60 || seoulData.stations.length !== 25) throw new Error('Unexpected Seoul district data.');
  const networkRecord = state.records.find(record => record.id === 'seoul');
  networkRecord.networkMean = true;
  networkRecord.label = 'Seoul · network mean';
  networkRecord.dataFile = 'data/seoul-stations-2024.json';
  networkRecord.localYear = {startUtc: seoulData.startUtc, intervalMinutes: 60, values: seoulData.network.values};
  for (const station of seoulData.stations) $('#seoul-record').append(element('option', station.name, {value: station.id}));
  const updateSeoulScope = record => {
    $('#seoul-scope').textContent = record.networkMean
      ? 'The network mean combines 25 district monitors (at least 20 reporting per hour). Choose a district for a site-level comparison with the U.S. reference levels.'
      : `${record.station.name}: one district monitor. Its measurements describe this location, not the whole city.`;
  };
  updateSeoulScope(networkRecord);
  $('#seoul-record').addEventListener('change', event => {
    let record = networkRecord;
    if (event.target.value !== 'network') {
      const station = seoulData.stations.find(item => item.id === event.target.value);
      record = validateRecord({...networkRecord, label: `Seoul · ${station.name}`, networkMean: false,
        values: station.values.slice(9).concat(Array(9).fill(null)), stationCounts: undefined,
        localYear: {startUtc: seoulData.startUtc, intervalMinutes: 60, values: station.values},
        station: {...networkRecord.station, id: station.sourceStationId, name: station.name, type: 'District monitoring station',
          aggregation: 'Hourly readings from one Seoul district monitor, supplied by Seoul Metropolitan Government.'},
        dataFile: 'data/seoul-stations-2024.json'});
    }
    state.records[state.records.findIndex(item => item.id === 'seoul')] = record;
    updateSeoulScope(record);
    sourceCards(state.records, manifest);
    render();
  });
  for (const [index, record] of state.records.entries()) {
    if (record.id === 'seoul' || index === 1) state.selected.add(record.id);
    const label = element('label', null, {class: 'air-city'});
    const input = element('input', null, {type: 'checkbox', value: record.id});
    input.checked = state.selected.has(record.id);
    input.addEventListener('change', () => { input.checked ? state.selected.add(record.id) : state.selected.delete(record.id); render(); });
    label.append(input, swatch(record.color), document.createTextNode(record.city));
    $('#city-options').append(label);
  }
  sourceCards(state.records, manifest);
  $('#average').addEventListener('change', event => { state.mode = event.target.value; render(); });
  const updateThreshold = event => {
    if (!event.target.validity.valid || event.target.value === '') {
      if (event.type === 'change') event.target.reportValidity();
      return;
    }
    if (state.threshold === Number(event.target.value)) return;
    state.threshold = Number(event.target.value);
    render();
  };
  $('#threshold').addEventListener('input', updateThreshold);
  $('#threshold').addEventListener('change', updateThreshold);
  $('#threshold-reset').addEventListener('click', () => { state.threshold = 35; $('#threshold').value = '35'; render(); });
  $('#day-basis').addEventListener('change', event => { state.basis = event.target.value; render(); });
  $('#distribution').addEventListener('change', event => { state.distributionMode = event.target.value; render(); });
  for (const id of ['from', 'through']) $(`#${id}`).addEventListener('change', () => {
    const first = (Date.parse($('#from').value + 'T00:00:00Z') - START_2024) / 3600000;
    const last = (Date.parse($('#through').value + 'T23:00:00Z') - START_2024) / 3600000;
    if (Number.isFinite(first) && Number.isFinite(last)) setRange(Math.min(first, last), Math.max(first, last));
  });
  $('#reset-range').addEventListener('click', () => setRange(0, HOURS_2024 - 1));
  for (const button of document.querySelectorAll('[data-month]')) button.addEventListener('click', () => {
    const month = Number(button.dataset.month);
    setRange((Date.UTC(2024, month, 1) - START_2024) / 3600000, (Date.UTC(2024, month + 1, 1) - START_2024) / 3600000 - 1);
  });
  $('#download').addEventListener('click', exportCsv);
  $('#download-comparison').addEventListener('click', () => downloadText(comparisonCsv(selectedRecords(), state), `pm25-comparison-${isoDate(state.first)}-to-${isoDate(state.last)}.csv`));
  $('#chart').addEventListener('pointermove', inspect);
  $('#chart').addEventListener('pointerleave', () => { if (dragStart === null) { $('#chart-tooltip').hidden = true; plot.cursor.setAttribute('visibility', 'hidden'); } });
  $('#chart').addEventListener('pointerdown', event => { if (event.pointerType !== 'touch') { dragStart = pointerHour(event); $('#chart').setPointerCapture(event.pointerId); } });
  $('#chart').addEventListener('pointerup', event => {
    if (dragStart === null) return;
    const end = pointerHour(event);
    const start = dragStart;
    dragStart = null;
    if (Math.abs(start - end) >= 24) setRange(Math.min(start, end), Math.max(start, end));
    else plot.brush.setAttribute('width', 0);
  });
  $('#chart').addEventListener('pointercancel', () => { dragStart = null; plot.brush.setAttribute('width', 0); });
  $('#load-status').textContent = `${state.records.length} archived records loaded. Seoul is selected.`;
  $('#explorer').hidden = false;
  let resizeTimer;
  window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 100); });
  render();
}

start().catch(error => {
  $('#load-status').textContent = `${error.message} Please reload the page or use the data downloads below.`;
  $('#load-status').className = 'air-error';
});
