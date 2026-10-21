import {dailyPairs, fitAssociation, predict, pearson, spearman} from './analysis.mjs';

const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const finite = Number.isFinite;
const fmt = (value, digits = 2) => finite(value) ? value.toLocaleString('en', {maximumFractionDigits: digits, minimumFractionDigits: digits}) : '—';
const integer = value => value.toLocaleString('en');
const avg = values => values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
const seasons = {DJF: {name: 'Winter · Dec–Feb', color: '#3463ad'}, MAM: {name: 'Spring · Mar–May', color: '#16766a'}, JJA: {name: 'Summer · Jun–Aug', color: '#bb542e'}, SON: {name: 'Autumn · Sep–Nov', color: '#8b549c'}};
const seasonOf = month => month === 12 || month <= 2 ? 'DJF' : month <= 5 ? 'MAM' : month <= 8 ? 'JJA' : 'SON';
const models = {linear: 'Linear', quadratic: 'Quadratic', monthAdjusted: 'Month-adjusted linear'};
const defaults = {city: 'seoul', seoul: 'seoul-network-mean', metric: 'temperature', basis: 'local', from: '2024-01-01', through: '2024-12-31', season: 'all', model: 'linear', pm: 35, heat: 30, direction: 'above'};
const state = {...defaults, manifest: null, records: [], supplement: null, current: null};
let resizeFrame;

function node(tag, text = null, attributes = {}) {
  const result = document.createElement(tag);
  if (text !== null) result.textContent = text;
  for (const [name, value] of Object.entries(attributes)) result.setAttribute(name, value);
  return result;
}

function svg(tag, attributes = {}, text = null) {
  const result = document.createElementNS(NS, tag);
  for (const [name, value] of Object.entries(attributes)) result.setAttribute(name, value);
  if (text !== null) result.textContent = text;
  return result;
}

function options(id, entries, selected) {
  $(id).replaceChildren(...entries.map(([value, label]) => node('option', label, {value})));
  $(id).value = selected;
}

function table(id, headers, rows, caption) {
  const target = $(id);
  const result = node('table');
  if (caption) result.append(node('caption', caption));
  const head = node('thead'), header = node('tr');
  for (const label of headers) header.append(node('th', label, {scope: 'col'}));
  head.append(header);
  const body = node('tbody');
  for (const cells of rows) {
    const row = node('tr');
    cells.forEach((text, index) => row.append(node(index === 0 ? 'th' : 'td', String(text ?? '—'), index === 0 ? {scope: 'row'} : {})));
    body.append(row);
  }
  result.append(head, body);
  target.replaceChildren(result);
}

function paragraph(target, text) { target.append(node('p', text)); }
function metricInfo() { return state.manifest.metrics[state.metric]; }
function metricLabel() { return metricInfo().label; }
function thermalUnit() { return state.metric === 'humidity' ? '%' : '°C'; }
function changeUnit() { return state.metric === 'humidity' ? 'percentage points' : '°C'; }
function defaultHeat(metric) { return metric === 'humidity' ? 80 : metric === 'utci' ? 32 : metric.startsWith('wbgt') ? 28 : 30; }

function pmSelection(record) {
  if (record.id !== 'seoul' || !state.supplement) return record.pmData;
  if (state.seoul === state.supplement.network.id) return record.pmData;
  const chosen = state.supplement.stations.find(station => station.id === state.seoul);
  if (!chosen) return record.pmData;
  return {...record.pmData, startUtc: state.supplement.startUtc, intervalMinutes: state.supplement.intervalMinutes,
    values: chosen.values, station: {...record.pmData.station, ...chosen, values: undefined}, sources: state.supplement.sources,
    timeConvention: state.supplement.timeConvention};
}

function getPairs(record) {
  const result = dailyPairs(pmSelection(record), record.heatData, {basis: state.basis, utcOffsetMinutes: record.utcOffsetHours * 60,
    heatMetric: state.metric, minHours: 18, from: state.from, through: state.through});
  const keep = day => state.season === 'all' || seasonOf(day.month) === state.season;
  const allDays = result.allDays.filter(keep), days = result.days.filter(keep);
  return {...result, days, allDays};
}

function paddedDomain(values, includeZero = false) {
  if (!values.length) return [0, 1];
  let low = Math.min(...values), high = Math.max(...values);
  if (includeZero) { low = Math.min(0, low); high = Math.max(0, high); }
  const pad = (high - low || Math.max(1, Math.abs(low) * 0.1)) * 0.07;
  return [low - pad, high + pad];
}

function chartFrame(id, xValues, yValues, xLabel, yLabel, {zeroY = false, nonnegativeY = false} = {}) {
  const chart = $(id), width = Math.max(310, chart.clientWidth || 1000), mobile = width < 600;
  const height = mobile ? 370 : 430;
  const box = {left: mobile ? 53 : 70, right: width - 22, top: mobile ? 46 : 35, bottom: height - (mobile ? 83 : 60)};
  const [xmin, xmax] = paddedDomain(xValues);
  let [ymin, ymax] = paddedDomain(yValues, zeroY);
  if (nonnegativeY) ymin = Math.max(0, ymin);
  const x = value => box.left + (value - xmin) / (xmax - xmin) * (box.right - box.left);
  const y = value => box.bottom - (value - ymin) / (ymax - ymin) * (box.bottom - box.top);
  chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
  const description = chart.querySelector('desc');
  chart.replaceChildren(svg('title', {}, `${yLabel} against ${xLabel}`));
  if (description) chart.append(description);
  const group = svg('g'); chart.append(group);
  for (let index = 0; index <= 4; index++) {
    const value = ymin + (ymax - ymin) * index / 4;
    group.append(svg('line', {x1: box.left, x2: box.right, y1: y(value), y2: y(value), stroke: '#dce4e5'}));
    group.append(svg('text', {x: box.left - 9, y: y(value) + 4, 'text-anchor': 'end'}, fmt(value, 1)));
  }
  for (let index = 0; index <= (mobile ? 3 : 5); index++) {
    const value = xmin + (xmax - xmin) * index / (mobile ? 3 : 5);
    group.append(svg('text', {x: x(value), y: box.bottom + 22, 'text-anchor': 'middle'}, fmt(value, 1)));
  }
  const addLabel = (text, attributes, maxCharacters) => {
    const lines = [''];
    for (const word of text.split(' ')) {
      if (lines.at(-1).length && lines.at(-1).length + word.length + 1 > maxCharacters) lines.push(word);
      else lines[lines.length - 1] += `${lines.at(-1) ? ' ' : ''}${word}`;
    }
    const label = svg('text', {...attributes, class: 'axis-label'});
    lines.forEach((line, index) => label.append(svg('tspan', {x: attributes.x, dy: index ? 14 : 0}, line)));
    group.append(label);
  };
  addLabel(yLabel, {x: box.left, y: 17}, mobile ? 34 : 100);
  addLabel(xLabel, {x: (box.left + box.right) / 2, y: box.bottom + 44, 'text-anchor': 'middle'}, mobile ? 39 : 110);
  return {chart, group, width, height, box, x, y, xmin, xmax, ymin, ymax};
}

function emptyChart(id, message) {
  const chart = $(id); chart.setAttribute('viewBox', '0 0 800 300');
  const description = chart.querySelector('desc');
  chart.replaceChildren(svg('text', {x: 400, y: 140, 'text-anchor': 'middle'}, message));
  if (description) chart.append(description);
}

function describeDay(day, departure = null) {
  return `${day.date}: PM₂.₅ ${fmt(day.pmMean, 1)} µg/m³; ${metricLabel()} ${fmt(day.heatMean, 1)} ${thermalUnit()}; ${day.pairedHours} paired hours${departure ? `; monthly departures ${fmt(departure.xDeparture, 1)} ${thermalUnit()} and ${fmt(departure.yDeparture, 1)} µg/m³` : ''}.`;
}

function attachPoint(circle, day, departure = null) {
  const description = describeDay(day, departure);
  circle.append(svg('title', {}, description));
  circle.setAttribute('aria-label', description);
  circle.setAttribute('tabindex', '0');
  const show = event => {
    const tooltip = $('scatter-tooltip');
    tooltip.textContent = description; tooltip.hidden = false;
    const bounds = circle.getBoundingClientRect();
    const x = finite(event.clientX) && event.type !== 'focus' ? event.clientX : bounds.x;
    const y = finite(event.clientY) && event.type !== 'focus' ? event.clientY : bounds.y;
    Object.assign(tooltip.style, {position: 'fixed', zIndex: 20, left: `${Math.max(8, Math.min(window.innerWidth - 290, x + 12))}px`, top: `${Math.max(8, Math.min(window.innerHeight - 130, y + 12))}px`, maxWidth: '275px', pointerEvents: 'none'});
  };
  circle.addEventListener('pointerenter', show);
  circle.addEventListener('focus', show);
  circle.addEventListener('pointerleave', () => { $('scatter-tooltip').hidden = true; });
  circle.addEventListener('blur', () => { $('scatter-tooltip').hidden = true; });
  const select = () => { $('selection-note').textContent = description; };
  circle.addEventListener('click', select);
  circle.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); } });
}

function drawScatter(days, fit) {
  const adjusted = state.model === 'monthAdjusted';
  $('selection-note').textContent = days.length ? 'Point to a day, or select a point for its date and paired-hour count.' : 'There are no eligible paired days in this selection.';
  $('scatter-tooltip').hidden = true;
  if (!days.length) { emptyChart('scatter', 'No paired days meet the completeness rule.'); return; }
  if (adjusted && !fit.available) { emptyChart('scatter', fit.reason); return; }
  const plotted = adjusted ? fit.predictions.map(row => ({...days.find(day => day.date === row.date), ...row, px: row.xDeparture, py: row.yDeparture}))
    : days.map(day => ({...day, px: day.heatMean, py: day.pmMean}));
  const xLabel = adjusted ? `${metricLabel()} · departure from monthly mean (${thermalUnit()})` : `${metricLabel()} · daily mean (${thermalUnit()})`;
  const yLabel = adjusted ? 'PM₂.₅ · departure from monthly mean (µg/m³)' : 'PM₂.₅ · daily mean (µg/m³)';
  const frame = chartFrame('scatter', plotted.map(day => day.px), plotted.map(day => day.py), xLabel, yLabel, {zeroY: adjusted, nonnegativeY: !adjusted});
  if (adjusted) {
    frame.group.append(svg('line', {x1: frame.x(0), x2: frame.x(0), y1: frame.box.top, y2: frame.box.bottom, stroke: '#9caeb5', 'stroke-dasharray': '4 4'}));
    frame.group.append(svg('line', {x1: frame.box.left, x2: frame.box.right, y1: frame.y(0), y2: frame.y(0), stroke: '#9caeb5', 'stroke-dasharray': '4 4'}));
  }
  const minimum = Math.min(...plotted.map(day => day.px)), maximum = Math.max(...plotted.map(day => day.px));
  if (fit.available) {
    let path = '';
    for (let index = 0; index <= 100; index++) {
      const xValue = minimum + (maximum - minimum) * index / 100;
      const yValue = adjusted ? fit.slope * xValue : predict(fit, xValue);
      path += `${index ? 'L' : 'M'}${frame.x(xValue).toFixed(2)},${frame.y(yValue).toFixed(2)}`;
    }
    const clipId = 'scatter-plot-clip';
    const defs = svg('defs'), clip = svg('clipPath', {id: clipId});
    clip.append(svg('rect', {x: frame.box.left, y: frame.box.top, width: frame.box.right - frame.box.left, height: frame.box.bottom - frame.box.top})); defs.append(clip); frame.chart.append(defs);
    frame.group.append(svg('path', {d: path, fill: 'none', stroke: '#17324d', 'stroke-width': 2.5, 'clip-path': `url(#${clipId})`}));
  }
  for (const [index, day] of plotted.entries()) {
    const circle = svg('circle', {cx: frame.x(day.px), cy: frame.y(day.py), r: 4, fill: seasons[seasonOf(day.month)].color, opacity: 0.73, stroke: '#fff', 'stroke-width': 0.6});
    attachPoint(circle, day, adjusted ? day : null);
    circle.setAttribute('tabindex', index === 0 ? '0' : '-1');
    circle.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const points = [...frame.group.querySelectorAll('circle')];
      const next = Math.max(0, Math.min(points.length - 1, index + (event.key === 'ArrowRight' ? 1 : -1)));
      for (const point of points) point.setAttribute('tabindex', '-1');
      points[next].setAttribute('tabindex', '0');
      points[next].focus();
    });
    frame.group.append(circle);
  }
}

function drawResiduals(fit) {
  if (!fit.available) { emptyChart('residual-chart', 'A fitted model is needed to show residuals.'); return; }
  const rows = fit.predictions;
  const chart = $('residual-chart'), width = Math.max(310, chart.clientWidth || 1000), height = width < 600 ? 260 : 300;
  const box = {left: 60, right: width - 20, top: 32, bottom: height - 42};
  const times = rows.map(row => Date.parse(row.date)), first = Math.min(...times), last = Math.max(...times);
  const [min, max] = paddedDomain(rows.map(row => row.residual), true);
  const x = value => box.left + (value - first) / Math.max(86400000, last - first) * (box.right - box.left);
  const y = value => box.bottom - (value - min) / (max - min) * (box.bottom - box.top);
  chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
  chart.replaceChildren(svg('title', {}, 'Daily PM₂.₅ residuals over the selected dates'));
  for (let index = 0; index <= 4; index++) {
    const value = min + (max - min) * index / 4;
    chart.append(svg('line', {x1: box.left, x2: box.right, y1: y(value), y2: y(value), stroke: '#dce4e5'}), svg('text', {x: box.left - 8, y: y(value) + 4, 'text-anchor': 'end'}, fmt(value, 1)));
  }
  chart.append(svg('line', {x1: box.left, x2: box.right, y1: y(0), y2: y(0), stroke: '#526a7b', 'stroke-width': 1.5}), svg('text', {x: box.left, y: 17}, 'Observed minus fitted PM₂.₅ · µg/m³'));
  for (let index = 0; index <= 3; index++) {
    const time = first + (last - first) * index / 3;
    chart.append(svg('text', {x: x(time), y: height - 13, 'text-anchor': index === 0 ? 'start' : index === 3 ? 'end' : 'middle'}, new Date(time).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC'})));
  }
  for (const row of rows) {
    const circle = svg('circle', {cx: x(Date.parse(row.date)), cy: y(row.residual), r: 3.1, fill: seasons[seasonOf(row.month)].color, opacity: 0.75});
    circle.append(svg('title', {}, `${row.date}: residual ${fmt(row.residual)} µg/m³; observed ${fmt(row.y)}, fitted ${fmt(row.fitted)}.`)); chart.append(circle);
  }
}

function renderCoverage(result) {
  const {allDays, days} = result;
  const expected = allDays.length * 24, pairHours = allDays.reduce((sum, day) => sum + day.pairedHours, 0);
  let selectedCalendarDays = 0;
  for (let time = Date.parse(state.from); time <= Date.parse(state.through); time += 86400000) {
    if (state.season === 'all' || seasonOf(new Date(time).getUTCMonth() + 1) === state.season) selectedCalendarDays++;
  }
  const items = [
    ['Days used', `${integer(days.length)} / ${integer(allDays.length)}`],
    ['Complete days within both archives', `${integer(allDays.length)} / ${integer(selectedCalendarDays)} selected calendar days`],
    ['Days with at least 18 valid PM₂.₅ hours', integer(allDays.filter(day => day.pmHours >= 18).length)],
    ['Days with at least 18 valid thermal hours', integer(allDays.filter(day => day.heatHours >= 18).length)],
    ['Days excluded · fewer than 18 paired hours', integer(allDays.length - days.length)],
    ['Paired hours across these complete days', `${integer(pairHours)} / ${integer(expected)}`],
    ['Daily means use', 'The same available hours for both exposures']
  ];
  const list = node('dl', null, {class: 'joint-coverage'});
  for (const [label, value] of items) { const item = node('div'); item.append(node('dt', label), node('dd', value)); list.append(item); }
  $('coverage').replaceChildren(list);
}

function modelRows(fits) {
  return Object.entries(fits).map(([key, fit]) => [models[key], fit.available ? String(fit.n) : `${fit.n} · unavailable`,
    fit.available ? `${fmt(fit.slopePer10)}${key === 'quadratic' ? ' at mean x' : ''}` : '—',
    fit.available ? `${fmt(fit.r2, 3)} · ${key === 'monthAdjusted' ? 'within month' : 'raw total'}` : fit.reason,
    fit.available ? fmt(fit.lag1.r, 3) : '—']);
}

function renderAssociations(days, fits) {
  const xs = days.map(day => day.heatMean), ys = days.map(day => day.pmMean);
  table('associations', ['Measure', 'Value'], [
    ['Paired days', integer(days.length)], ['Mean PM₂.₅ · µg/m³', fmt(avg(ys), 1)], [`Mean ${metricLabel()} · ${thermalUnit()}`, fmt(avg(xs), 1)],
    ['Pearson r · raw daily pairs', fmt(pearson(xs, ys), 3)], ['Spearman ρ · raw daily pairs', fmt(spearman(xs, ys), 3)],
    ['Pearson r · monthly means removed', fmt(fits.monthAdjusted.rWithin, 3)], ['Spearman ρ · monthly means removed', fmt(fits.monthAdjusted.rhoWithin, 3)]
  ], 'Selected city and dates');
  table('models', ['Model', 'Days', `PM₂.₅ change per 10 ${changeUnit()} · µg/m³`, 'R² and basis', 'Residual lag-one r'], modelRows(fits), 'Separate descriptive fits for this city');
  const fit = fits[state.model];
  $('model-note').textContent = !fit.available ? fit.reason : state.model === 'monthAdjusted'
    ? `This fit gives each observed month its own intercept. The plotted values subtract the selected sample's monthly means from both exposures. The slope describes changes within a month; its R² (${fmt(fit.r2, 3)}) uses within-month PM₂.₅ variation. Total R², including month differences, is ${fmt(fit.totalR2, 3)}.`
    : state.model === 'quadratic' ? `The quadratic curve allows an association to bend. Its reported change per 10 ${changeUnit()} is the local slope at the selected days' mean x (${fmt(fit.slopeAt, 1)} ${thermalUnit()}); it is not a constant effect across the curve.`
      : `The line describes the average association over these paired days: ${fmt(fit.slopePer10)} µg/m³ per 10 ${changeUnit()}. It is not a causal effect.`;
  table('diagnostics', ['Diagnostic', 'Value'], [
    ['Consecutive-day residual correlation', fit.available ? fmt(fit.lag1.r, 3) : '—'],
    ['Consecutive-day pairs used', fit.available ? integer(fit.lag1.pairs) : '—'],
    ['Largest Cook’s distance', fit.available ? fmt(fit.maxCooksDistance, 3) : '—'],
    ['Residual degrees of freedom', fit.available ? integer(fit.residualDf) : '—']
  ], 'Residual checks for the selected model');
}

function renderComparison() {
  const adjusted = state.model === 'monthAdjusted';
  const rows = state.records.map(record => {
    const {days} = getPairs(record), fit = fitAssociation(days, {model: state.model});
    const label = record.id === 'seoul' ? `Seoul · ${pmSelection(record).station.name}` : record.city;
    return [label, integer(days.length), fmt(adjusted ? fit.rWithin : fit.r, 3),
      fmt(adjusted ? fit.rhoWithin : fit.rho, 3), fit.available ? fmt(fit.slopePer10) : '—', fit.available ? fmt(fit.r2, 3) : '—'];
  });
  table('comparison', ['City / PM₂.₅ monitor', 'Days', `Pearson r${adjusted ? ' · within month' : ' · raw'}`, `Spearman ρ${adjusted ? ' · within month' : ' · raw'}`, `Change per 10 ${changeUnit()}`, adjusted ? 'Within-month R²' : 'Raw total R²'], rows,
    `Each city fitted separately · ${models[state.model]}${state.model === 'quadratic' ? ' (slope at each city’s mean x)' : ''}`);
}

function renderCounts(days) {
  const thermalSymbol = state.direction === 'below' ? '≤' : '≥';
  $('heat-threshold-label').textContent = `${metricLabel()} daily mean ${thermalSymbol} (${thermalUnit()})`;
  if (!finite(state.pm) || !finite(state.heat)) { $('joint-counts').replaceChildren(node('p', 'Enter two numeric thresholds to count days.')); return; }
  const counts = [0, 0, 0, 0];
  for (const day of days) counts[(day.pmMean >= state.pm ? 2 : 0) + ((state.direction === 'below' ? day.heatMean <= state.heat : day.heatMean >= state.heat) ? 1 : 0)]++;
  table('joint-counts', ['Conditions met', 'Days', 'Share of eligible paired days'], [
    ['Both conditions', integer(counts[3]), days.length ? `${fmt(counts[3] / days.length * 100, 1)}%` : '—'],
    ['PM₂.₅ only', integer(counts[2]), days.length ? `${fmt(counts[2] / days.length * 100, 1)}%` : '—'],
    ['Thermal condition only', integer(counts[1]), days.length ? `${fmt(counts[1] / days.length * 100, 1)}%` : '—'],
    ['Neither condition', integer(counts[0]), days.length ? `${fmt(counts[0] / days.length * 100, 1)}%` : '—']
  ], `${integer(days.length)} eligible paired days · PM₂.₅ ≥ ${fmt(state.pm, 1)} µg/m³ and ${metricLabel()} ${thermalSymbol} ${fmt(state.heat, 1)} ${thermalUnit()}. Equality is included.`);
}

function renderSources(record, pm) {
  const target = $('sources'); target.replaceChildren();
  const pmCard = node('article'), heatCard = node('article');
  pmCard.append(node('h3', 'PM₂.₅ observations'));
  paragraph(pmCard, `${record.city} · ${pm.station?.name || pm.station?.id || 'monitor record'}. ${record.pm.qaStatus || pm.quality?.qaStatus || 'See the source notes for quality status.'}`);
  if (record.id === 'seoul') paragraph(pmCard, state.seoul === state.supplement?.network.id ? 'The network mean is unweighted and requires at least 20 of 25 monitors in an hour. It is not population-weighted exposure.' : 'Changing a district monitor changes the pollution series. All Seoul districts use the same city-centred weather grid; these are not district-specific temperatures.');
  if (record.id === 'pyeongtaek') paragraph(pmCard, 'The archive includes zeros and a summer data gap. Zeros are retained as reported; they are not independently confirmed clean-air episodes.');
  if (record.id === 'los-angeles') paragraph(pmCard, 'This is the North Main Street continuous monitor, POC 3. It is distinct from the site’s primary daily regulatory monitor. Reported values and quality flags follow the EPA source archive.');
  const source = pm.sources?.[0], sourceUrl = pm.station?.url || source?.pageUrl || source?.url;
  if (sourceUrl) pmCard.append(node('a', 'PM₂.₅ source', {href: sourceUrl, target: '_blank', rel: 'noopener noreferrer'}));
  if (pm.timeConvention?.interpretation_limit) paragraph(pmCard, pm.timeConvention.interpretation_limit);
  heatCard.append(node('h3', 'Gridded weather estimates'));
  paragraph(heatCard, `ERA5 via Open-Meteo · grid centre ${record.heatData.gridLatitude}°, ${record.heatData.gridLongitude}°. This represents weather over a broader area than the pollution monitor; it does not resolve a street, workplace or personal exposure.`);
  paragraph(heatCard, metricInfo().method);
  if (state.metric === 'utci') paragraph(heatCard, `This series is not the ERA5-HEAT product. Across the full archive, ${integer(record.heatData.diagnostics.utciWindFloorHours)} hours had wind raised to the UTCI minimum of 0.5 m/s.`);
  if (state.metric.startsWith('wbgt')) paragraph(heatCard, 'WBGT omits hours outside the application’s property-fit filter. The retained daily sample therefore favours conditions where this calculation is available. Missing estimates are not treated as low exposure. WBGT does not describe cold stress.');
  heatCard.append(node('a', 'Weather source and calculations', {href: '../heat-stress/data/README.md'}));
  target.append(pmCard, heatCard);
}

function readControls() {
  for (const id of ['city', 'metric', 'basis', 'from', 'through', 'season', 'model']) state[id] = $(id).value;
  state.seoul = $('seoul-record').value;
  state.direction = $('thermal-direction').value;
  state.pm = $('pm-threshold').value.trim() ? Number($('pm-threshold').value) : NaN;
  state.heat = $('heat-threshold').value.trim() ? Number($('heat-threshold').value) : NaN;
}

function query() {
  const params = new URLSearchParams();
  for (const key of Object.keys(defaults)) if (finite(state[key]) || typeof state[key] === 'string') params.set(key, String(state[key]));
  return params;
}

function render() {
  if (!state.manifest) return;
  readControls();
  $('seoul-control').hidden = state.city !== 'seoul';
  const record = state.records.find(item => item.id === state.city), pm = pmSelection(record);
  $('record-note').textContent = `${record.city} · ${pm.station?.name || 'PM₂.₅ monitor'} · ${state.basis === 'utc' ? 'UTC days' : `local standard-time days (UTC${record.utcOffsetHours >= 0 ? '+' : ''}${record.utcOffsetHours})`}.`;
  $('metric-note').textContent = state.metric === 'utci' ? 'UTCI assumes mean radiant temperature equals air temperature. It is a controlled radiation scenario, not the published ERA5-HEAT series.' : state.metric.startsWith('wbgt') ? 'WBGT means use only retained model hours. Days with fewer than 18 paired hours are excluded; winter coverage can be limited.' : 'Both daily means use the same valid hourly timestamps. A day needs at least 18 paired hours.';
  $('plot-note').textContent = state.model === 'monthAdjusted' ? 'Each point is one eligible day after subtracting its month’s mean from both exposures. Colours show meteorological seasons; the line is the within-month association.' : 'Each point is one eligible day. Colours show meteorological seasons. The fitted line or curve stays inside the observed temperature or humidity range.';
  if (state.from > state.through || !/^2024-\d{2}-\d{2}$/.test(state.from) || !/^2024-\d{2}-\d{2}$/.test(state.through)) {
    $('load-status').textContent = 'Choose a valid date range within 2024, with the start date before the end date.';
    for (const id of ['coverage', 'associations', 'models', 'diagnostics', 'comparison', 'joint-counts', 'daily-table']) $(id).replaceChildren();
    for (const id of ['model-note', 'selection-note']) $(id).textContent = '';
    $('scatter-tooltip').hidden = true;
    for (const id of ['download', 'download-model', 'copy-link']) $(id).disabled = true;
    emptyChart('scatter', 'Choose a valid 2024 date range.'); emptyChart('residual-chart', 'Choose a valid 2024 date range.');
    state.current = null; return;
  }
  $('load-status').textContent = '';
  for (const id of ['download', 'download-model', 'copy-link']) $(id).disabled = false;
  const result = getPairs(record), days = result.days;
  const fits = Object.fromEntries(Object.keys(models).map(model => [model, fitAssociation(days, {model})]));
  state.current = {record, pm, result, fits};
  renderCoverage(result); drawScatter(days, fits[state.model]); renderAssociations(days, fits); drawResiduals(fits[state.model]); renderComparison(); renderCounts(days); renderSources(record, pm);
  const predictions = new Map(fits[state.model].predictions.map(row => [row.date, row]));
  table('daily-table', ['Date', 'PM₂.₅ · µg/m³', `${metricLabel()} · ${thermalUnit()}`, 'PM hours', 'Thermal hours', 'Paired hours', 'Included', 'Fitted PM₂.₅', 'Residual'], result.allDays.map(day => [day.date, fmt(day.pmMean, 2), fmt(day.heatMean, 2), day.pmHours, day.heatHours, day.pairedHours, day.eligible ? 'Yes' : 'No · fewer than 18 paired hours', fmt(predictions.get(day.date)?.fitted, 2), fmt(predictions.get(day.date)?.residual, 2)]), 'Daily pairing and completeness');
  history.replaceState(null, '', `${location.pathname}?${query()}${location.hash}`);
}

function csvCell(value) { const text = value === null || value === undefined || typeof value === 'number' && !finite(value) ? '' : String(value); return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; }
function saveCsv(rows, filename) {
  const blob = new Blob(['\uFEFF', rows.map(row => row.map(csvCell).join(',')).join('\r\n')], {type: 'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob), link = node('a', null, {href: url, download: filename});
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  $('download-status').textContent = `${filename} downloaded.`;
}

function downloadDays() {
  if (!state.current) return;
  const {record, pm, result, fits} = state.current;
  const predictions = new Map(fits[state.model].predictions.map(row => [row.date, row]));
  const rows = [['city', 'pm_monitor', 'date', 'day_season', 'selected_season', 'calendar_basis', 'fixed_utc_offset_hours', 'thermal_metric', 'thermal_unit', 'pm_mean_ug_m3', 'thermal_mean', 'pm_valid_hours', 'thermal_valid_hours', 'paired_hours', 'expected_hours', 'included', 'pm_threshold_ug_m3', 'thermal_direction', 'thermal_threshold', 'model', 'fitted_pm_ug_m3', 'residual_pm_ug_m3', 'pm_source', 'weather_source']];
  for (const day of result.allDays) {
    const prediction = predictions.get(day.date);
    rows.push([record.city, pm.station?.name, day.date, seasonOf(day.month), state.season, state.basis, state.basis === 'utc' ? 0 : record.utcOffsetHours, metricLabel(), thermalUnit(), day.pmMean, day.heatMean, day.pmHours, day.heatHours, day.pairedHours, day.expectedHours, day.eligible, state.pm, state.direction, state.heat, state.model, prediction?.fitted, prediction?.residual, pm.station?.url || pm.sources?.[0]?.pageUrl || pm.sources?.[0]?.url, record.heatData.source.url]);
  }
  saveCsv(rows, `air-heat-${state.city}-${state.metric}-${state.basis}-${state.from}-${state.through}.csv`);
}

function downloadModels() {
  if (!state.current) return;
  const {record, pm, fits} = state.current;
  const rows = [['city', 'pm_monitor', 'metric', 'unit', 'basis', 'from', 'through', 'season', 'model', 'available', 'reason', 'n_days', 'slope_per_10_units', 'slope_evaluated_at_x', 'r_squared', 'r_squared_basis', 'total_r_squared', 'pearson_r_raw', 'spearman_rho_raw', 'pearson_r_within_month', 'spearman_rho_within_month', 'residual_lag1_r', 'residual_lag1_pairs', 'max_cooks_distance', 'coefficients']];
  for (const [model, fit] of Object.entries(fits)) rows.push([record.city, pm.station?.name, metricLabel(), thermalUnit(), state.basis, state.from, state.through, state.season, model, fit.available, fit.reason, fit.n, fit.slopePer10, fit.slopeAt, fit.r2, fit.r2Basis, fit.totalR2, fit.r, fit.rho, fit.rWithin, fit.rhoWithin, fit.lag1.r, fit.lag1.pairs, fit.maxCooksDistance, JSON.stringify(fit.coefficients)]);
  saveCsv(rows, `air-heat-models-${state.city}-${state.metric}-${state.from}-${state.through}.csv`);
}

async function fetchJson(path) {
  const response = await fetch(new URL(path, import.meta.url));
  if (!response.ok) throw new Error(`Could not load ${path} (${response.status}).`);
  return response.json();
}

async function start() {
  try {
    $('load-status').textContent = 'Loading 2024 pollution and weather data…';
    const manifest = await fetchJson('./data/manifest.json'); state.manifest = manifest;
    const [records, supplement] = await Promise.all([
      Promise.all(manifest.records.map(async record => ({...record, pmData: await fetchJson(record.pm.file), heatData: await fetchJson(record.heat.file)}))),
      manifest.seoulStations ? fetchJson(manifest.seoulStations.file) : null
    ]);
    state.records = records; state.supplement = supplement;
    for (const record of records) {
      if (!Array.isArray(record.pmData.values) || !Object.keys(manifest.metrics).every(metric => Array.isArray(record.heatData.values[metric]))) throw new Error(`The archived data for ${record.city} have an unexpected format.`);
    }
    const params = new URLSearchParams(location.search);
    for (const key of Object.keys(defaults)) if (params.has(key)) state[key] = typeof defaults[key] === 'number' ? Number(params.get(key)) : params.get(key);
    if (!records.some(record => record.id === state.city)) state.city = defaults.city;
    if (!manifest.metrics[state.metric]) state.metric = defaults.metric;
    if (!['local', 'utc'].includes(state.basis)) state.basis = defaults.basis;
    if (!['all', ...Object.keys(seasons)].includes(state.season)) state.season = defaults.season;
    if (!models[state.model]) state.model = defaults.model;
    if (!['above', 'below'].includes(state.direction)) state.direction = defaults.direction;
    if (!params.has('heat')) state.heat = defaultHeat(state.metric);
    const stationEntries = supplement ? [[supplement.network.id, supplement.network.name], ...supplement.stations.map(station => [station.id, station.name]).sort((a, b) => a[1].localeCompare(b[1]))] : [];
    if (!stationEntries.some(([id]) => id === state.seoul)) state.seoul = stationEntries[0]?.[0] || '';
    options('city', records.map(record => [record.id, record.city]), state.city);
    options('seoul-record', stationEntries, state.seoul);
    options('metric', Object.entries(manifest.metrics).map(([key, info]) => [key, info.label]), state.metric);
    options('basis', [['local', 'Local standard time'], ['utc', 'UTC']], state.basis);
    options('season', [['all', 'All seasons'], ...Object.entries(seasons).map(([key, info]) => [key, info.name])], state.season);
    options('model', Object.entries(models), state.model);
    options('thermal-direction', [['above', 'At or above'], ['below', 'At or below']], state.direction);
    for (const id of ['from', 'through']) $(id).value = state[id];
    $('pm-threshold').value = finite(state.pm) ? state.pm : defaults.pm; $('heat-threshold').value = finite(state.heat) ? state.heat : defaultHeat(state.metric);
    $('legend').replaceChildren(...Object.values(seasons).map(info => { const item = node('span', null, {class: 'joint-legend-item'}); item.append(node('span', '', {class: 'air-swatch', style: `--series:${info.color}`}), document.createTextNode(info.name)); return item; }));
    $('explorer').hidden = false;
    for (const id of ['city', 'seoul-record', 'metric', 'basis', 'from', 'through', 'season', 'model', 'pm-threshold', 'heat-threshold', 'thermal-direction']) $(id).addEventListener('change', () => {
      if (id === 'metric') $('heat-threshold').value = defaultHeat($('metric').value);
      try { render(); } catch (error) { $('load-status').textContent = `The selection could not be analysed: ${error.message}`; }
    });
    for (const id of ['pm-threshold', 'heat-threshold']) $(id).addEventListener('input', () => {
      try { render(); } catch (error) { $('load-status').textContent = `The selection could not be analysed: ${error.message}`; }
    });
    $('download').addEventListener('click', downloadDays); $('download-model').addEventListener('click', downloadModels);
    $('copy-link').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(location.href); $('download-status').textContent = 'Link copied with the current selections.'; }
      catch { $('download-status').textContent = 'Copy the address from your browser to share these selections.'; }
    });
    window.addEventListener('resize', () => { cancelAnimationFrame(resizeFrame); resizeFrame = requestAnimationFrame(() => { if (state.current) { drawScatter(state.current.result.days, state.current.fits[state.model]); drawResiduals(state.current.fits[state.model]); } }); });
    render();
  } catch (error) {
    $('load-status').textContent = `The archived data could not be loaded. ${error.message} Please reload the page.`;
    console.error(error);
  }
}

start();
