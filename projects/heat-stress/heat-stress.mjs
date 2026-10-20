import {HOURS_2024, START_2024, aggregate, summarize, quantile, counts, monthly, hourlyProfile, utciCategories, exceedanceSteps} from './analysis.mjs';

const $ = selector => document.querySelector(selector);
const NS = 'http://www.w3.org/2000/svg';
const HOUR = 3600000;
const COLORS = {seoul: '#16766a', pyeongtaek: '#7c4897', london: '#3463ad', beijing: '#a94f30', 'los-angeles': '#87701b'};
const METRICS = {
  temperature: {label: 'Air temperature', unit: '°C', threshold: 30, presets: [25, 30, 35], min: -60, max: 70,
    note: 'Air temperature at 2 m above the ERA5 model surface. This measure does not include the effects of humidity, wind or radiant heat.'},
  humidity: {label: 'Relative humidity', unit: '%', threshold: 80, presets: [60, 80, 90], min: 0, max: 100,
    note: 'Relative humidity at 2 m above the model surface. High humidity alone does not imply high heat stress; interpret it alongside temperature.'},
  utci: {label: 'UTCI · no added radiant heat', unit: '°C', threshold: 32, presets: [26, 32, 38, 46], min: -80, max: 80,
    note: 'UTCI combines temperature, humidity and 10 m wind with mean radiant temperature set equal to air temperature. This scenario omits added radiant heat from sunlight or hot surfaces. Wind below 0.5 m/s is raised to 0.5 m/s; values outside the polynomial’s domain are missing.'},
  wbgt: {label: 'WBGT · exposed outdoors', unit: '°C', threshold: 28, presets: [25, 28, 30, 32], min: -60, max: 70,
    note: 'Outdoor WBGT is estimated with the Liljegren energy-balance model, including modeled shortwave radiation. WBGT is omitted where the model’s evaporation property fit would be extrapolated. Means summarize eligible hours, not the whole year; compare coverage. This is not a measured workplace WBGT or a universal safety threshold.'},
  wbgtShade: {label: 'WBGT · no shortwave radiation', unit: '°C', threshold: 28, presets: [25, 28, 30, 32], min: -60, max: 70,
    note: 'This WBGT scenario removes shortwave radiation at the modeled sensors, retaining the ambient wind profile and longwave assumptions. WBGT is omitted where the model’s evaporation property fit would be extrapolated. Means summarize eligible hours, not the whole year; compare coverage. This does not reconstruct shade at a particular site.'},
};
const MODES = new Set(['hourly', 'dailyMean', 'dailyMax', 'dailyMin', 'rolling8', 'rolling24']);
const state = {records: [], selected: new Set(['seoul', 'pyeongtaek', 'los-angeles']), metric: 'temperature',
  mode: 'dailyMean', basis: 'local', threshold: 30, first: 0, last: HOURS_2024 - 1, indexCity: 'seoul'};
let plot = null;
let validInputs = true;

const format = value => !Number.isFinite(value) ? '—' : value.toLocaleString('en', {minimumFractionDigits: 1, maximumFractionDigits: 1});
const integer = value => value.toLocaleString('en');
const isoDate = hour => new Date(START_2024 + hour * HOUR).toISOString().slice(0, 10);
const shortDate = hour => new Intl.DateTimeFormat('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC'}).format(START_2024 + hour * HOUR);
const monthName = month => new Intl.DateTimeFormat('en', {month: 'short', timeZone: 'UTC'}).format(Date.UTC(2024, month, 1));
const offset = record => state.basis === 'local' ? record.utcOffsetHours : 0;
const selected = () => state.records.filter(record => state.selected.has(record.id));
const metric = () => METRICS[state.metric];
const element = (tag, text = null, attributes = {}) => {
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
const swatch = color => element('span', '', {class: 'air-swatch', style: `--series:${color}`, 'aria-hidden': 'true'});
function cityCell(record) {
  const node = element('th', null, {scope: 'row'});
  node.append(swatch(record.color), document.createTextNode(record.city));
  return node;
}
function emptyRow(body, columns, message = 'Choose at least one city above.') {
  const row = element('tr');
  row.append(element('td', message, {colspan: columns}));
  body.append(row);
}
function finiteValues(record, key = state.metric) {
  return record.values[key].slice(state.first, state.last + 1);
}
function parseDate(value) {
  if (!/^2024-\d{2}-\d{2}$/.test(value)) return null;
  const timestamp = Date.parse(`${value}T00:00:00Z`);
  if (!Number.isFinite(timestamp) || new Date(timestamp).toISOString().slice(0, 10) !== value) return null;
  return (timestamp - START_2024) / HOUR;
}
function validateRecord(record, entry) {
  if (record.id !== entry.id || record.year !== 2024 || record.intervalMinutes !== 60 || Date.parse(record.startUtc) !== START_2024) {
    throw new Error(`Unexpected time grid for ${entry.city || entry.id}.`);
  }
  if (typeof record.city !== 'string' || !Number.isFinite(record.utcOffsetHours)) throw new Error('Invalid city metadata.');
  for (const key of Object.keys(METRICS)) {
    const values = record.values?.[key];
    if (!Array.isArray(values) || values.length !== HOURS_2024 || !values.every(value => value === null || Number.isFinite(value))) {
      throw new Error(`Invalid ${key} data for ${record.city}.`);
    }
    if (key === 'humidity' && !values.every(value => value === null || value >= 0 && value <= 100)) {
      throw new Error(`Relative humidity is outside 0–100% for ${record.city}.`);
    }
  }
  return {...record, color: COLORS[record.id] || '#654d82', file: entry.file || entry.path};
}

function readQuery() {
  const params = new URLSearchParams(location.search);
  if (Object.hasOwn(METRICS, params.get('metric'))) state.metric = params.get('metric');
  state.threshold = metric().threshold;
  if (MODES.has(params.get('average'))) state.mode = params.get('average');
  if (['utc', 'local'].includes(params.get('basis'))) state.basis = params.get('basis');
  const threshold = params.get('threshold');
  if (threshold !== null && threshold.trim() !== '' && Number.isFinite(Number(threshold))
    && Number(threshold) >= metric().min && Number(threshold) <= metric().max) state.threshold = Number(threshold);
  if (params.has('cities')) {
    const available = new Set(state.records.map(record => record.id));
    state.selected = new Set(params.get('cities').split(',').filter(id => available.has(id)));
  }
  const first = parseDate(params.get('from') || '2024-01-01');
  const last = parseDate(params.get('through') || '2024-12-31');
  if (first !== null && last !== null && first <= last) { state.first = first; state.last = last + 23; }
  if (state.records.some(record => record.id === params.get('city'))) state.indexCity = params.get('city');
}

function setupControls() {
  const choices = $('#city-options');
  for (const record of state.records) {
    const label = element('label', null, {class: 'air-city'});
    const input = element('input', null, {type: 'checkbox', value: record.id});
    input.checked = state.selected.has(record.id);
    input.addEventListener('change', () => {
      if (input.checked) state.selected.add(record.id); else state.selected.delete(record.id);
      render();
    });
    label.append(input, swatch(record.color), document.createTextNode(record.city));
    choices.append(label);
  }
  $('#metric').value = state.metric;
  $('#average').value = state.mode;
  $('#basis').value = state.basis;
  $('#from').value = isoDate(state.first);
  $('#through').value = isoDate(state.last);
  $('#metric').addEventListener('change', event => {
    state.metric = event.target.value;
    state.threshold = metric().threshold;
    updateThresholdControls();
    updateInputValidity();
  });
  $('#average').addEventListener('change', event => { state.mode = event.target.value; render(); });
  $('#basis').addEventListener('change', event => { state.basis = event.target.value; render(); });
  for (const id of ['from', 'through', 'threshold']) $(`#${id}`).addEventListener('change', updateInputValidity);
  $('#reset-range').addEventListener('click', () => setRange(0, HOURS_2024 - 1));
  document.querySelectorAll('[data-month]').forEach(button => button.addEventListener('click', () => {
    const month = Number(button.dataset.month);
    setRange((Date.UTC(2024, month, 1) - START_2024) / HOUR, (Date.UTC(2024, month + 1, 1) - START_2024) / HOUR - 1);
  }));
  $('#index-city').addEventListener('change', event => { state.indexCity = event.target.value; renderIndices(selected()); });
  $('#download').addEventListener('click', exportHourly);
  $('#download-stats').addEventListener('click', exportComparison);
  $('#copy-link').addEventListener('click', copyLink);
  $('#chart').addEventListener('pointermove', inspect);
  $('#chart').addEventListener('pointerleave', () => {
    $('#chart-tooltip').hidden = true;
    if (plot?.cursor) plot.cursor.setAttribute('visibility', 'hidden');
  });
  updateThresholdControls();
}

function updateThresholdControls() {
  const measure = metric();
  $('#threshold-label').textContent = `Threshold (${measure.unit})`;
  $('#threshold').min = measure.min;
  $('#threshold').max = measure.max;
  $('#threshold').value = state.threshold;
  $('#threshold').setCustomValidity('');
  $('#threshold').removeAttribute('aria-invalid');
  $('#metric-note').textContent = measure.note;
  const presets = $('#threshold-presets');
  presets.replaceChildren(element('span', 'Try:'));
  for (const value of measure.presets) {
    const button = element('button', `${value} ${measure.unit}`, {type: 'button'});
    button.addEventListener('click', () => { $('#threshold').value = value; updateInputValidity(); });
    presets.append(button);
  }
}

function updateInputValidity() {
  const from = $('#from');
  const through = $('#through');
  const thresholdInput = $('#threshold');
  [from, through, thresholdInput].forEach(input => { input.setCustomValidity(''); input.removeAttribute('aria-invalid'); });
  const first = parseDate(from.value);
  const last = parseDate(through.value);
  const threshold = thresholdInput.value.trim() === '' ? NaN : Number(thresholdInput.value);
  let message = '';
  let input = null;
  if (first === null) { message = 'Choose a start date in 2024.'; input = from; }
  else if (last === null) { message = 'Choose an end date in 2024.'; input = through; }
  else if (first > last) { message = 'The start date must be on or before the end date.'; input = through; }
  else if (!Number.isFinite(threshold) || threshold < metric().min || threshold > metric().max) {
    message = `Enter a threshold between ${metric().min} and ${metric().max} ${metric().unit}.`; input = thresholdInput;
  }
  validInputs = !message;
  if (message) {
    input.setCustomValidity(message);
    input.setAttribute('aria-invalid', 'true');
    $('#selection-note').textContent = `${message} The plots still show the last valid selection.`;
    $('#selection-note').setAttribute('role', 'alert');
    updateActionButtons();
    return;
  }
  $('#selection-note').removeAttribute('role');
  state.first = first;
  state.last = last + 23;
  state.threshold = threshold;
  render();
}
function setRange(first, last) {
  $('#from').value = isoDate(first);
  $('#through').value = isoDate(last);
  updateInputValidity();
}
function updateActionButtons() {
  const disabled = !validInputs || !selected().length;
  for (const id of ['download', 'download-stats', 'copy-link']) $(`#${id}`).disabled = disabled;
}

function chartBase(id, height = 330, minimumWidth = 290) {
  const chart = $(`#${id}`);
  const width = Math.max(minimumWidth, chart.clientWidth || (id === 'chart' ? 1120 : 600));
  chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
  chart.replaceChildren();
  if (id === 'chart') chart.append(svg('desc', {id: 'chart-desc'}, 'Selected city records over time. Missing or ineligible values leave gaps. Numerical summaries and downloadable data follow.'));
  const group = svg('g');
  chart.append(group);
  return {chart, group, width, height, left: width < 420 ? 43 : 58, right: width - 20, top: 34, bottom: height - 48};
}
function niceStep(span, ticks = 5) {
  const rough = Math.max(span, .1) / ticks;
  const power = 10 ** Math.floor(Math.log10(rough));
  const base = rough / power;
  return (base <= 1 ? 1 : base <= 2 ? 2 : base <= 5 ? 5 : 10) * power;
}
function numericAxis(box, low, high, label) {
  const step = niceStep(high - low);
  const floor = Math.floor(low / step) * step;
  const ceiling = Math.ceil(high / step) * step;
  const y = value => box.bottom - (value - floor) / Math.max(step, ceiling - floor) * (box.bottom - box.top);
  for (let tick = floor; tick <= ceiling + step / 100; tick += step) {
    box.group.append(svg('line', {x1: box.left, x2: box.right, y1: y(tick), y2: y(tick), stroke: '#e2e6e4'}),
      svg('text', {x: box.left - 9, y: y(tick) + 4, 'text-anchor': 'end'}, Math.abs(tick) < .00001 ? '0' : String(Number(tick.toFixed(2)))));
  }
  box.group.append(svg('text', {x: box.left, y: 18, class: 'axis-label'}, label));
  return {y, floor, ceiling};
}
function noData(box, message = 'Choose at least one city above.') {
  box.group.append(svg('text', {x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2, 'text-anchor': 'middle'}, message));
}
function appendPath(box, points, x, y, record) {
  let path = '';
  let open = false;
  for (const point of points) {
    if (!Number.isFinite(point.value)) { open = false; continue; }
    path += `${open ? 'L' : 'M'}${x(point.hour).toFixed(2)},${y(point.value).toFixed(2)}`;
    open = true;
  }
  const node = svg('path', {d: path, fill: 'none', stroke: record.color, 'stroke-width': 1.8, 'stroke-linejoin': 'round', 'aria-label': record.city});
  box.group.append(node);
}
function drawTimeSeries(records) {
  const box = chartBase('chart', $('#chart').clientWidth < 600 ? 320 : 400);
  const series = records.map(record => ({record, points: aggregate(record.values[state.metric], state.mode, offset(record), state.first, state.last)}));
  let low = Infinity;
  let high = -Infinity;
  for (const {points} of series) for (const point of points) {
    if (point.value !== null) { low = Math.min(low, point.value); high = Math.max(high, point.value); }
  }
  const hasValues = Number.isFinite(low);
  if (!hasValues) { low = 0; high = 10; }
  if (high === low) { low -= 1; high += 1; }
  const {y, floor, ceiling} = numericAxis(box, low, high, `${metric().label} · ${metric().unit}`);
  const span = Math.max(1, state.last - state.first);
  const x = hour => box.left + (hour - state.first) / span * (box.right - box.left);
  if (state.threshold >= floor && state.threshold <= ceiling) {
    box.group.append(svg('line', {x1: box.left, x2: box.right, y1: y(state.threshold), y2: y(state.threshold), class: 'air-threshold-line'}),
      svg('text', {x: box.right - 3, y: y(state.threshold) - 6, 'text-anchor': 'end', class: 'air-threshold-label'}, `${format(state.threshold)} ${metric().unit}`));
  }
  if (span > 24 * 90) {
    for (let month = 0; month < 12; month += box.width < 600 ? 2 : 1) {
      const hour = (Date.UTC(2024, month, 1) - START_2024) / HOUR;
      if (hour >= state.first && hour <= state.last) box.group.append(svg('text', {x: x(hour), y: box.height - 19}, monthName(month)));
    }
  } else {
    const ticks = box.width < 600 ? 2 : 4;
    for (let index = 0; index <= ticks; index++) {
      const hour = state.first + span * index / ticks;
      box.group.append(svg('text', {x: x(hour), y: box.height - 19, 'text-anchor': index === 0 ? 'start' : index === ticks ? 'end' : 'middle'}, shortDate(hour)));
    }
  }
  for (const {record, points} of series) appendPath(box, points, x, y, record);
  if (!records.length) noData(box);
  else if (!hasValues) noData(box, 'No eligible values in this selection.');
  const cursor = svg('line', {x1: 0, x2: 0, y1: box.top, y2: box.bottom, stroke: '#17324d', 'stroke-dasharray': '3 4', visibility: 'hidden'});
  box.group.append(cursor);
  plot = {box, series, x, span, cursor};
  box.chart.setAttribute('aria-label', `${metric().label}, ${$('#average').selectedOptions[0].textContent}, ${shortDate(state.first)} through ${shortDate(state.last)} 2024`);
}

function inspect(event) {
  if (!plot?.series.length) return;
  const rect = $('#chart').getBoundingClientRect();
  const pointer = (event.clientX - rect.left) / rect.width * plot.box.width;
  const hour = Math.max(state.first, Math.min(state.last, state.first + (pointer - plot.box.left) / (plot.box.right - plot.box.left) * plot.span));
  plot.cursor.setAttribute('x1', plot.x(hour));
  plot.cursor.setAttribute('x2', plot.x(hour));
  plot.cursor.setAttribute('visibility', 'visible');
  const tooltip = $('#chart-tooltip');
  const timestamp = new Date(START_2024 + Math.round(hour) * HOUR).toISOString();
  tooltip.replaceChildren(element('strong', `${timestamp.slice(0, 10)} ${timestamp.slice(11, 16)} UTC`));
  for (const {record, points} of plot.series) {
    let nearest = null;
    for (const point of points) if (!nearest || Math.abs(point.hour - hour) < Math.abs(nearest.hour - hour)) nearest = point;
    const row = element('div');
    let time = '';
    if (state.mode.startsWith('daily') && nearest) {
      time = ` · ${isoDate(nearest.hour + offset(record))} ${state.basis === 'local' ? 'local day' : 'UTC day'}`;
    }
    row.append(swatch(record.color), document.createTextNode(`${record.city}: ${format(nearest?.value)}${Number.isFinite(nearest?.value) ? ` ${metric().unit}` : ''}${time}`));
    tooltip.append(row);
  }
  tooltip.hidden = false;
}

function renderSummary(records) {
  const body = $('#summary tbody');
  body.replaceChildren();
  const expected = state.last - state.first + 1;
  for (const record of records) {
    const stats = summarize(finiteValues(record));
    const row = element('tr');
    row.append(cityCell(record), element('td', `${integer(stats.count)} / ${integer(expected)} (${format(stats.count / expected * 100)}%)`));
    for (const key of ['mean', 'median', 'p95', 'max']) row.append(element('td', format(stats[key])));
    body.append(row);
  }
  if (!records.length) emptyRow(body, 6);
  $('#summary caption').textContent = `Selected period · hourly ${metric().label.toLowerCase()} (${metric().unit})`;
}
function renderCounts(records, results) {
  const body = $('#counts tbody');
  const rolling = $('#rolling-counts tbody');
  body.replaceChildren();
  rolling.replaceChildren();
  for (const record of records) {
    const data = results.get(record.id).counts;
    const row = element('tr');
    row.append(cityCell(record));
    for (const key of ['hoursAtOrAbove', 'percent', 'longestRun', 'daysAny', 'daysMean', 'daysMin', 'validDays']) {
      const cell = element('td', key === 'percent' ? format(data[key]) : integer(data[key]));
      if (key === 'daysAny') cell.append(element('span', `of ${integer(data.daysWithHours)} dates with data`, {class: 'capture'}));
      row.append(cell);
    }
    body.append(row);
    const windows = element('tr');
    windows.append(cityCell(record), element('td', `${integer(data.rolling8AtOrAbove)} / ${integer(data.validRolling8)} valid`),
      element('td', `${integer(data.rolling24AtOrAbove)} / ${integer(data.validRolling24)} valid`));
    rolling.append(windows);
  }
  if (!records.length) { emptyRow(body, 8); emptyRow(rolling, 3); }
  $('#counts caption').textContent = `${metric().label} ≥ ${format(state.threshold)} ${metric().unit} · selected period`;
  $('#threshold-note').textContent = state.metric === 'utci'
    ? 'UTCI shortcuts follow published heat-stress category boundaries for the no-added-radiant-heat scenario. Counts are comparisons, not safety determinations.'
    : state.metric.startsWith('wbgt') ? 'WBGT shortcuts are exploratory values. There is no single action threshold that applies to every workload, clothing ensemble and acclimatization status.'
      : 'These shortcuts are exploratory values for comparing conditions. They are not regulatory limits or universal health thresholds.';
}
function renderPatternTables(records, results) {
  const body = $('#monthly tbody');
  body.replaceChildren();
  for (let month = 0; month < 12; month++) for (const record of records) {
    const data = results.get(record.id).months[month];
    if (!data.expected) continue;
    const row = element('tr');
    row.append(element('th', monthName(month), {scope: 'row'}), element('td', record.city), element('td', format(data.mean)),
      element('td', format(data.max)), element('td', `${integer(data.hoursAtOrAbove)} (${data.count ? format(data.hoursAtOrAbove / data.count * 100) : '—'}%)`),
      element('td', `${integer(data.count)} / ${integer(data.expected)}`));
    body.append(row);
  }
  if (!records.length) emptyRow(body, 6);
  $('#monthly caption').textContent = `UTC months · ${metric().label} (${metric().unit}) · threshold ≥ ${format(state.threshold)} ${metric().unit}`;
  const header = element('tr');
  header.append(element('th', state.basis === 'local' ? 'Local standard-time hour' : 'UTC hour', {scope: 'col'}));
  for (const record of records) header.append(element('th', record.city, {scope: 'col'}));
  $('#clock-table thead').replaceChildren(header);
  const clockBody = $('#clock-table tbody');
  clockBody.replaceChildren();
  if (!records.length) emptyRow(clockBody, 1);
  else for (let hour = 0; hour < 24; hour++) {
    const row = element('tr');
    row.append(element('th', `${String(hour).padStart(2, '0')}:00`, {scope: 'row'}));
    for (const record of records) {
      const data = results.get(record.id).profile[hour];
      row.append(element('td', data.count ? `${format(data.hoursAtOrAbove / data.count * 100)}% (${integer(data.hoursAtOrAbove)} / ${integer(data.count)})` : 'No valid hours'));
    }
    clockBody.append(row);
  }
  $('#clock-title').textContent = `Hour of the day · ${state.basis === 'local' ? 'local standard time' : 'UTC'}`;
}
function drawFrequency(id, records, results, kind) {
  const box = chartBase(id, 310);
  const isMonth = kind === 'months';
  const length = isMonth ? 12 : 24;
  const series = records.map(record => ({record, points: results.get(record.id)[kind].map((data, index) => ({hour: index,
    value: data.count ? data.hoursAtOrAbove / data.count * 100 : null}))}));
  let maximum = 0;
  const hasValues = series.some(({points}) => points.some(point => point.value !== null));
  for (const {points} of series) for (const point of points) if (point.value !== null) maximum = Math.max(maximum, point.value);
  const {y} = numericAxis(box, 0, Math.max(10, maximum), '% of valid hours at or above threshold');
  const x = index => box.left + index / (length - 1) * (box.right - box.left);
  for (let index = 0; index < length; index++) {
    if (isMonth && box.width < 480 && index % 2 || !isMonth && ![0, 6, 12, 18, 23].includes(index)) continue;
    box.group.append(svg('text', {x: x(index), y: box.height - 20, 'text-anchor': index === 0 ? 'start' : index === length - 1 ? 'end' : 'middle'}, isMonth ? monthName(index) : `${String(index).padStart(2, '0')}`));
  }
  for (const {record, points} of series) {
    appendPath(box, points, x, y, record);
    for (const point of points) if (point.value !== null) {
      const circle = svg('circle', {cx: x(point.hour), cy: y(point.value), r: 2.6, fill: record.color});
      circle.append(svg('title', {}, `${record.city} · ${isMonth ? monthName(point.hour) : `${point.hour}:00`}: ${format(point.value)}%`));
      box.group.append(circle);
    }
  }
  if (!records.length) noData(box);
  else if (!hasValues) noData(box, 'No eligible values in this selection.');
  box.chart.setAttribute('aria-label', `${isMonth ? 'Monthly' : 'Hourly'} shares of valid ${metric().label.toLowerCase()} values at or above ${state.threshold} ${metric().unit}. Numerical values follow in the ${isMonth ? 'monthly' : 'hourly pattern'} table.`);
}

function distributionTable() {
  if ($('#distribution-table')) return;
  const details = element('details', null, {class: 'air-months'});
  details.append(element('summary', 'Distribution values'));
  const scroll = element('div', null, {class: 'air-table-scroll'});
  const table = element('table', null, {id: 'distribution-table'});
  table.append(element('caption', 'Hourly values at selected percentiles'), element('thead'), element('tbody'));
  scroll.append(table);
  details.append(scroll);
  $('#distribution-chart').after(details);
}
function drawDistribution(records, results) {
  distributionTable();
  const box = chartBase('distribution-chart', 350);
  const data = records.map(record => ({record, values: finiteValues(record).filter(Number.isFinite).sort((a, b) => a - b)}));
  let low = Infinity;
  let high = -Infinity;
  for (const {values} of data) if (values.length) { low = Math.min(low, values[0]); high = Math.max(high, values.at(-1)); }
  const hasValues = Number.isFinite(low);
  if (!hasValues) { low = 0; high = 10; }
  if (high === low) { low -= 1; high += 1; }
  const {y, floor, ceiling} = numericAxis(box, low, high, `${metric().label} · ${metric().unit}`);
  const x = percent => box.left + percent / 100 * (box.right - box.left);
  for (const value of [0, 25, 50, 75, 100]) box.group.append(svg('text', {x: x(value), y: box.height - 27,
    'text-anchor': value === 0 ? 'start' : value === 100 ? 'end' : 'middle'}, `${value}%`));
  box.group.append(svg('text', {x: (box.left + box.right) / 2, y: box.height - 8, 'text-anchor': 'middle', class: 'axis-label'}, 'Share of valid hourly values at or above this value'));
  if (state.threshold >= floor && state.threshold <= ceiling) box.group.append(svg('line', {x1: box.left, x2: box.right, y1: y(state.threshold), y2: y(state.threshold), class: 'air-threshold-line'}));
  for (const {record, values} of data) {
    const points = exceedanceSteps(values);
    let path = '';
    for (let index = 0; index < points.length; index++) {
      const point = points[index];
      if (!index) path = `M${x(point.percent).toFixed(2)},${y(point.value).toFixed(2)}`;
      else path += point.value === points[index - 1].value ? `H${x(point.percent).toFixed(2)}` : `V${y(point.value).toFixed(2)}`;
    }
    box.group.append(svg('path', {d: path, fill: 'none', stroke: record.color, 'stroke-width': 1.8, 'aria-label': record.city}));
    const result = results.get(record.id).counts;
    if (result.validHours && state.threshold >= floor && state.threshold <= ceiling) {
      const dot = svg('circle', {cx: x(result.percent), cy: y(state.threshold), r: 4, fill: record.color, stroke: 'white', 'stroke-width': 1});
      dot.append(svg('title', {}, `${record.city}: ${integer(result.hoursAtOrAbove)} / ${integer(result.validHours)} valid hours (${format(result.percent)}%) at or above ${format(state.threshold)} ${metric().unit}`));
      box.group.append(dot);
    }
  }
  if (!records.length) noData(box);
  else if (!hasValues) noData(box, 'No eligible values in this selection.');
  const header = element('tr');
  header.append(element('th', `Percentile (${metric().unit})`, {scope: 'col'}));
  for (const record of records) header.append(element('th', record.city, {scope: 'col'}));
  $('#distribution-table thead').replaceChildren(header);
  const body = $('#distribution-table tbody');
  body.replaceChildren();
  if (!records.length) emptyRow(body, 1);
  else for (const probability of [0, .05, .1, .25, .5, .75, .9, .95, 1]) {
    const row = element('tr');
    row.append(element('th', probability === 0 ? 'Minimum' : probability === 1 ? 'Maximum' : `${probability * 100}th`, {scope: 'row'}));
    for (const {values} of data) row.append(element('td', format(quantile(values, probability))));
    body.append(row);
  }
  $('#distribution-table caption').textContent = `${metric().label} · selected period · interpolated percentiles of valid hourly values`;
}

function renderIndices(records) {
  const select = $('#index-city');
  if (!records.some(record => record.id === state.indexCity)) state.indexCity = records[0]?.id || '';
  select.replaceChildren();
  for (const record of records) select.append(element('option', record.city, {value: record.id}));
  select.value = state.indexCity;
  select.disabled = !records.length;
  const body = $('#indices tbody');
  body.replaceChildren();
  const record = records.find(item => item.id === state.indexCity);
  if (record) for (const [key, measure] of Object.entries(METRICS)) {
    const stats = summarize(finiteValues(record, key));
    const row = element('tr');
    row.append(element('th', `${measure.label} (${measure.unit})`, {scope: 'row'}), element('td', format(stats.mean)),
      element('td', format(stats.p95)), element('td', format(stats.max)), element('td', `${integer(stats.count)} / ${integer(state.last - state.first + 1)}`));
    body.append(row);
  }
  else emptyRow(body, 5);
  $('#indices caption').textContent = `${record?.city || 'Selected city'} · selected period · WBGT means cover eligible hours only; compare hours available`;
  const categoryBody = $('#categories tbody');
  categoryBody.replaceChildren();
  for (const city of records) {
    const {count: validHours, bins} = utciCategories(finiteValues(city, 'utci'));
    const row = element('tr');
    const name = cityCell(city);
    name.append(element('span', `${integer(validHours)} valid UTCI hours`, {class: 'capture'}));
    row.append(name);
    for (const count of bins) row.append(element('td', `${integer(count)} (${validHours ? format(count / validHours * 100) : '—'}%)`));
    categoryBody.append(row);
  }
  if (!records.length) emptyRow(categoryBody, 6);
}

function sourceCards() {
  const container = $('#sources');
  container.replaceChildren();
  for (const record of state.records) {
    const article = element('article');
    article.append(element('h4', record.city));
    const coordinate = (latitude, longitude) => Number.isFinite(latitude) && Number.isFinite(longitude)
      ? `${latitude.toFixed(2)}°, ${longitude.toFixed(2)}°` : 'See data record';
    const offsetLabel = `UTC${record.utcOffsetHours >= 0 ? '+' : ''}${record.utcOffsetHours}`;
    article.append(element('p', `City reference: ${coordinate(record.latitude, record.longitude)}. ERA5 grid: ${coordinate(record.gridLatitude, record.gridLongitude)}. Calendar days use ${offsetLabel} when local standard time is selected.`));
    const coverage = Object.entries(METRICS).map(([key, measure]) => `${measure.label}: ${integer(record.values[key].filter(Number.isFinite).length)} / ${integer(HOURS_2024)} hours`);
    article.append(element('p', coverage.join('; ') + '.'));
    const diagnostics = record.diagnostics || {};
    if (Number.isFinite(diagnostics.utciWindFloorHours)) article.append(element('p', `UTCI wind floor applied: ${integer(diagnostics.utciWindFloorHours)} hours. Outside the UTCI domain: ${integer(diagnostics.utciOutsideDomainHours || 0)} hours. Missing UTCI: ${integer(diagnostics.utciMissingHours || 0)} hours.`));
    if (Number.isFinite(diagnostics.wbgtNonconvergentHours)) article.append(element('p', `WBGT solver failures: ${integer(diagnostics.wbgtNonconvergentHours)} outdoors; ${integer(diagnostics.wbgtShadeNonconvergentHours || 0)} without shortwave radiation. These hours remain gaps.`));
    if (Number.isFinite(diagnostics.wbgtOutsidePropertyFitHours)) article.append(element('p', `WBGT omitted to avoid extrapolating the evaporation property fit: ${integer(diagnostics.wbgtOutsidePropertyFitHours)} hours outdoors; ${integer(diagnostics.wbgtShadeOutsidePropertyFitHours || 0)} without shortwave radiation. WBGT means and percentages summarize the remaining eligible hours.`));
    const link = element('a', 'City data (JSON)', {href: record.file});
    article.append(element('p'));
    article.lastChild.append(link);
    container.append(article);
  }
}

function render() {
  const records = selected();
  const results = new Map(records.map(record => [record.id, {
    counts: counts(record.values[state.metric], state.threshold, offset(record), state.first, state.last),
    months: monthly(record.values[state.metric], state.threshold, offset(record), state.first, state.last),
    profile: hourlyProfile(record.values[state.metric], state.threshold, offset(record), state.first, state.last),
  }]));
  $('#chart-tooltip').hidden = true;
  $('#legend').replaceChildren(...records.map(record => {
    const item = element('span');
    item.append(swatch(record.color), document.createTextNode(record.city));
    return item;
  }));
  drawTimeSeries(records);
  renderSummary(records);
  renderCounts(records, results);
  renderPatternTables(records, results);
  drawFrequency('monthly-chart', records, results, 'months');
  drawFrequency('clock-chart', records, results, 'profile');
  drawDistribution(records, results);
  renderIndices(records);
  if (validInputs) $('#selection-note').textContent = records.length
    ? `${shortDate(state.first)}–${shortDate(state.last)} 2024 · ${records.map(record => record.city).join(', ')} · ${metric().unit}`
    : 'Choose at least one city above.';
  $('#chart-note').textContent = `${$('#average').selectedOptions[0].textContent}. ${state.mode.startsWith('daily')
    ? 'Daily groups require 18 valid hours and all 24 hourly timestamps within the selected range.'
    : state.mode.startsWith('rolling') ? 'Trailing means require a complete selected window and at least 75% usable values.'
      : 'Individual hourly estimates are shown.'} The vertical axis adjusts to the selection and can include negative values. The dashed line is the chosen threshold, when within the plotted range.`;
  updateActionButtons();
}

const csvCell = value => {
  const text = value === null || value === undefined ? '' : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
const csvRow = values => values.map(csvCell).join(',');
function downloadCsv(rows, filename) {
  const blob = new Blob(['\uFEFF', rows.map(csvRow).join('\r\n'), '\r\n'], {type: 'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = element('a', '', {href: url, download: filename});
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $('#download-status').textContent = `Downloaded ${filename}. Missing values are blank; times are UTC.`;
}
function exportHourly() {
  if (!validInputs || !selected().length) return;
  const rows = [['timestamp_utc', 'city', 'record_id', 'temperature_c', 'relative_humidity_percent', 'utci_no_added_radiant_heat_c',
    'wbgt_outdoor_c', 'wbgt_no_shortwave_c', 'utci_assumption', 'weather_source']];
  for (const record of selected()) for (let hour = state.first; hour <= state.last; hour++) rows.push([
    new Date(START_2024 + hour * HOUR).toISOString(), record.city, record.id,
    ...Object.keys(METRICS).map(key => record.values[key][hour]), 'Mean radiant temperature equals air temperature; wind floor 0.5 m/s; domain limits applied', 'ERA5 via Open-Meteo',
  ]);
  downloadCsv(rows, `heat-hourly-${isoDate(state.first)}-to-${isoDate(state.last)}.csv`);
}
function exportComparison() {
  if (!validInputs || !selected().length) return;
  const rows = [['city', 'record_id', 'measure', 'unit', 'from_utc', 'through_utc', 'calendar_basis', 'daily_utc_offset_hours',
    'threshold_at_or_above', 'expected_hours', 'valid_hours', 'mean', 'median', 'p95', 'min', 'max', 'hours_at_or_above',
    'percent_valid_hours_at_or_above', 'longest_run_hours', 'dates_with_observed_hours', 'valid_18_hour_complete_days', 'observed_dates_any_hour_at_or_above', 'days_mean_at_or_above',
    'days_minimum_at_or_above', 'valid_8h_windows', '8h_windows_at_or_above', 'valid_24h_windows', '24h_windows_at_or_above', 'index_assumption']];
  for (const record of selected()) {
    const stats = summarize(finiteValues(record));
    const result = counts(record.values[state.metric], state.threshold, offset(record), state.first, state.last);
    rows.push([record.city, record.id, state.metric, metric().unit, isoDate(state.first), isoDate(state.last), state.basis,
      offset(record), state.threshold, state.last - state.first + 1, stats.count, stats.mean, stats.median, stats.p95, stats.min, stats.max,
      result.hoursAtOrAbove, result.percent, result.longestRun, result.daysWithHours, result.validDays, result.daysAny, result.daysMean, result.daysMin,
      result.validRolling8, result.rolling8AtOrAbove, result.validRolling24, result.rolling24AtOrAbove, metric().note]);
  }
  downloadCsv(rows, `heat-comparison-${state.metric}-${isoDate(state.first)}-to-${isoDate(state.last)}.csv`);
}
async function copyLink() {
  if (!validInputs) return;
  const url = new URL(location.href);
  url.search = '';
  url.searchParams.set('cities', selected().map(record => record.id).join(','));
  url.searchParams.set('metric', state.metric);
  url.searchParams.set('average', state.mode);
  url.searchParams.set('basis', state.basis);
  url.searchParams.set('from', isoDate(state.first));
  url.searchParams.set('through', isoDate(state.last));
  url.searchParams.set('threshold', state.threshold);
  if (state.indexCity) url.searchParams.set('city', state.indexCity);
  history.replaceState(null, '', url);
  try {
    await navigator.clipboard.writeText(url.href);
    $('#download-status').textContent = 'Link copied. It includes the selected cities, measure, dates, averaging period and threshold.';
  } catch {
    const link = element('a', 'Link to this view', {href: url.href});
    $('#download-status').replaceChildren(document.createTextNode('The view is saved in the address bar. '), link);
  }
}

async function boot() {
  const response = await fetch(new URL('data/manifest.json', import.meta.url));
  if (!response.ok) throw new Error('The data manifest could not be loaded.');
  const manifest = await response.json();
  if (manifest.year !== 2024 || !Array.isArray(manifest.records) || !manifest.records.length) throw new Error('The data manifest is incomplete.');
  state.records = await Promise.all(manifest.records.map(async entry => {
    const file = entry.file || entry.path;
    if (typeof file !== 'string') throw new Error('A city data file is missing from the manifest.');
    const data = await fetch(new URL(file, import.meta.url));
    if (!data.ok) throw new Error(`Weather data for ${entry.city || entry.id} could not be loaded.`);
    return validateRecord(await data.json(), entry);
  }));
  readQuery();
  setupControls();
  sourceCards();
  $('#explorer').hidden = false;
  $('#load-status').hidden = true;
  render();
  let resizeFrame = null;
  new ResizeObserver(() => {
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => { resizeFrame = null; render(); });
  }).observe($('#chart').parentElement);
}

boot().catch(error => {
  $('#explorer').hidden = true;
  const status = $('#load-status');
  status.hidden = false;
  status.classList.add('air-error');
  status.setAttribute('role', 'alert');
  status.textContent = `${error.message} Reload this page to try again, or use the data files and source notes below.`;
  console.error(error);
});
