import {dailyPairs} from './analysis.mjs';

const NS = 'http://www.w3.org/2000/svg';
const $ = id => document.getElementById(id);
const finite = Number.isFinite;
const fmt = (value, digits = 2) => finite(value) ? value.toLocaleString('en', {minimumFractionDigits: digits, maximumFractionDigits: digits}) : '—';
const seasonNames = {winter: 'Winter · Jan–Feb, Dec', spring: 'Spring · Mar–May', summer: 'Summer · Jun–Aug', autumn: 'Autumn · Sep–Nov'};
const colors = {winter: '#3463ad', spring: '#16766a', summer: '#bb542e', autumn: '#8b549c'};
const seasonOf = month => month <= 2 || month === 12 ? 'winter' : month <= 5 ? 'spring' : month <= 8 ? 'summer' : 'autumn';
const modelNames = {monthOnly: 'Month differences', weatherAdjusted: 'Month + weather', distributedLag: 'Month + weather + thermal lags 0–3', priorPmSensitivity: 'Lags + previous-day PM₂.₅'};
const interpretation = {
  seoul: 'Wind, humidity and precipitation account for much of the positive within-month association. Allowing curved wind and humidity terms gives a similar result. The seasonal temperature curves show a net rise in winter, declines in spring and autumn, and little change in summer; one annual slope conceals those differences.',
  pyeongtaek: 'The positive within-month UTCI association largely disappears after weather adjustment. Lag estimates vary with the specification and uncertainty bandwidth. Missing days reduce the common sample substantially, and only 15 August days support the summer curve. These results do not support a firm direction for an independent thermal association.',
  london: 'Positive estimates in the main weather models weaken when wind and humidity can curve, or when previous-day pollution is included. The pattern is sensitive to how weather and pollution persistence are modeled. Temperature and UTCI also give different winter curves.',
  beijing: 'The positive adjusted association persists with curved wind and humidity terms and after conditioning on previous-day pollution, although the estimates become smaller. Seasonal curves differ, and individual lag coefficients should not be assigned atmospheric mechanisms. The result describes this monitor and year.',
  'los-angeles': 'The positive adjusted association persists with curved wind and humidity terms. Conditioning on previous-day pollution reduces the lag sum, while its interval remains positive in the main specification. The seasonal temperature curve is much flatter in summer than in spring; higher thermal conditions do not have one uniform association across the year.'
};
const element = (tag, text, attrs = {}) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
};
const svg = (tag, attrs = {}, text) => {
  const node = document.createElementNS(NS, tag);
  if (text !== undefined) node.textContent = text;
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
};
const interval = result => `${fmt(result.estimate)} (${fmt(result.ci95[0])} to ${fmt(result.ci95[1])})`;
function table(id, headings, rows, caption) {
  const node = element('table'), head = element('thead'), body = element('tbody'), header = element('tr');
  node.append(element('caption', caption));
  headings.forEach(text => header.append(element('th', text, {scope: 'col'}))); head.append(header);
  rows.forEach(values => { const row = element('tr'); values.forEach((value, i) => row.append(element(i ? 'td' : 'th', String(value), i ? {} : {scope: 'row'}))); body.append(row); });
  node.append(head, body); $(id).replaceChildren(node);
}

function drawSeasons(city, metric, pairedDays) {
  const panels = city.seasonal[metric], target = $('seasonal-curves'); target.replaceChildren();
  const label = metric === 'utci' ? 'UTCI (°C)' : 'Temperature (°C)';
  const ymax = Math.max(1, ...pairedDays.map(day => day.pmMean), ...panels.flatMap(panel => panel.curve.flatMap(point => [point.y, point.span50Y, point.span80Y])));
  for (const panel of panels) {
    const figure = element('figure'); figure.append(element('figcaption', `${seasonNames[panel.season]} · ${panel.n} days`));
    const chart = svg('svg', {class: 'joint-small-chart', role: 'img', 'aria-label': `${city.city}, ${seasonNames[panel.season]}: PM₂.₅ against ${label}`});
    const columns = window.innerWidth > 760 ? 2 : 1;
    const width = Math.max(270, ((target.clientWidth || 1000) - (columns === 2 ? 20 : 0)) / columns - 34);
    const height = 330, left = 55, right = width - 15, top = 30, bottom = 270;
    chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
    chart.append(svg('title', {}, `${seasonNames[panel.season]} local linear smooth; solid span 65%, dashed 50% and 80%.`));
    const [xmin, xmax] = panel.xRange, span = xmax - xmin || 1;
    const x = value => left + (value - xmin) / span * (right - left), y = value => bottom - value / (ymax * 1.04) * (bottom - top);
    chart.append(svg('text', {x: left, y: 16}, 'PM₂.₅ (µg/m³)'));
    for (let tick = 0; tick <= 4; tick++) {
      const value = ymax * tick / 4;
      chart.append(svg('line', {x1: left, x2: right, y1: y(value), y2: y(value), stroke: '#dce4e5'}), svg('text', {x: left - 8, y: y(value) + 4, 'text-anchor': 'end'}, fmt(value, 0)));
      const xv = xmin + span * tick / 4;
      chart.append(svg('text', {x: x(xv), y: bottom + 21, 'text-anchor': 'middle'}, fmt(xv, 1)));
    }
    const days = pairedDays.filter(day => seasonOf(day.month) === panel.season);
    for (const day of days) {
      const dot = svg('circle', {cx: x(day.heatMean), cy: y(day.pmMean), r: 2.7, fill: colors[panel.season], opacity: .35});
      dot.append(svg('title', {}, `${day.date}: ${fmt(day.heatMean, 1)} °C; ${fmt(day.pmMean, 1)} µg/m³`)); chart.append(dot);
    }
    for (const key of ['span50Y', 'span80Y', 'y']) {
      chart.append(svg('path', {d: panel.curve.map((point, i) => `${i ? 'L' : 'M'} ${x(point.x)} ${y(point[key])}`).join(' '), fill: 'none', stroke: colors[panel.season], 'stroke-width': key === 'y' ? 3 : 1.3, 'stroke-dasharray': key === 'y' ? '' : '5 4', opacity: key === 'y' ? 1 : .7}));
    }
    chart.append(svg('text', {x: (left + right) / 2, y: height - 13, 'text-anchor': 'middle'}, label));
    figure.append(chart, element('p', `Displayed smooth: ${fmt(panel.centralRange[0], 1)} to ${fmt(panel.centralRange[1], 1)} °C.`, {class: 'air-note'})); target.append(figure);
  }
  table('seasonal-summary', ['Season', 'Days', 'Mean PM₂.₅ · µg/m³', 'Pearson r', 'Smooth endpoint change · µg/m³', 'Changes with span 50% / 80%'], panels.map(panel => [seasonNames[panel.season], panel.n, fmt(panel.meanPm, 1), fmt(panel.r, 3), fmt(panel.curve.at(-1).y - panel.curve[0].y), `${fmt(panel.curve.at(-1).span50Y - panel.curve[0].span50Y)} / ${fmt(panel.curve.at(-1).span80Y - panel.curve[0].span80Y)}`]), 'Endpoint changes compare the fitted 90th-percentile value with the 10th-percentile value within each season; they are not a common temperature increment or a test of monotonicity.');
  $('seasonal-finding').textContent = `The PM₂.₅ scale is shared across panels; thermal ranges differ by season. Curves describe unadjusted seasonal pairs and can still reflect changes within a season. Winter combines January–February with December. ${city.id === 'pyeongtaek' ? 'Pyeongtaek has only 15 eligible August days, limiting its summer curve.' : 'Dashed lines show smoothing choices rather than sampling uncertainty.'}`;
}

function drawLags(model, metric) {
  const chart = $('lag-chart'), width = Math.max(330, chart.clientWidth || 950), height = 370;
  const left = 68, right = width - 24, top = 45, bottom = 290;
  const rows = [...model.lags, model.cumulative];
  let low = Math.min(0, ...rows.map(row => row.ci95[0])), high = Math.max(0, ...rows.map(row => row.ci95[1]));
  const pad = (high - low || 1) * .12; low -= pad; high += pad;
  const y = value => bottom - (value - low) / (high - low) * (bottom - top);
  chart.setAttribute('viewBox', `0 0 ${width} ${height}`); chart.replaceChildren(svg('title', {}, 'Distributed-lag coefficients and the lag 0–3 sum, with approximate 95% Newey–West intervals.'));
  chart.append(svg('text', {x: left, y: 18}, 'PM₂.₅ change (µg/m³ per °C)'));
  for (let tick = 0; tick <= 4; tick++) {
    const value = low + (high - low) * tick / 4;
    chart.append(svg('line', {x1: left, x2: right, y1: y(value), y2: y(value), stroke: '#dce4e5'}), svg('text', {x: left - 10, y: y(value) + 4, 'text-anchor': 'end'}, fmt(value)));
  }
  chart.append(svg('line', {x1: left, x2: right, y1: y(0), y2: y(0), stroke: '#526676', 'stroke-dasharray': '5 4'}));
  const labels = ['Today', '1 day earlier', '2 days earlier', '3 days earlier', 'Lag 0–3 sum'];
  rows.forEach((row, i) => {
    const x = left + (right - left) * (i + .5) / 5;
    chart.append(svg('line', {x1: x, x2: x, y1: y(row.ci95[0]), y2: y(row.ci95[1]), stroke: '#17324d', 'stroke-width': 2}));
    for (const bound of row.ci95) chart.append(svg('line', {x1: x - 6, x2: x + 6, y1: y(bound), y2: y(bound), stroke: '#17324d', 'stroke-width': 2}));
    const dot = svg('circle', {cx: x, cy: y(row.estimate), r: 5, fill: i === 4 ? '#a35830' : '#16766a'}); dot.append(svg('title', {}, `${labels[i]}: ${interval(row)}`)); chart.append(dot);
    const text = svg('text', {x, y: bottom + 25, 'text-anchor': 'middle'});
    const words = width < 650 ? labels[i].replace(' earlier', '').split(' ') : [labels[i]];
    words.forEach((word, j) => text.append(svg('tspan', {x, dy: j ? 14 : 0}, word))); chart.append(text);
  });
}

function renderModels(city, metric) {
  const models = city.models[metric];
  const chosen = [['monthOnly', models.monthOnly.current, 'Current day'], ['weatherAdjusted', models.weatherAdjusted.current, 'Current day'], ['distributedLag', models.distributedLag.cumulative, 'Lag 0–3 sum'], ['priorPmSensitivity', models.priorPmSensitivity.cumulative, 'Lag 0–3 sum']];
  table('adjusted-models', ['Model', 'Days', 'Thermal contrast', 'Estimate (95% HAC interval)', 'Partial R² · thermal terms', 'Residual lag-1 r'], chosen.map(([key, result, contrast]) => [modelNames[key], models[key].n, contrast, interval(result), `${fmt(models[key].partialR2 * 100, 1)}%`, fmt(models[key].residualLag1, 3)]), 'PM₂.₅ change in µg/m³ per 1°C · all rows use the same eligible dates · approximate 95% Newey–West intervals, bandwidth 7 calendar days.');
  $('adjustment-finding').textContent = `${models.matchedN} dates have eligible pairs for today and all three previous calendar days, out of ${models.dailyN} daily pairs. Weather controls are current-day wind and humidity means plus log(1 + daily precipitation). Partial R² is the extra variation explained by thermal terms after that row’s other controls; the lag models contain four thermal terms, so it is not a like-for-like model ranking.`;
  drawLags(models.distributedLag, metric);
  table('lag-table', ['Thermal predictor', 'Estimate (95% HAC interval)', 'Variance inflation after month removal'], models.distributedLag.lags.map((result, i) => [i ? `${i} calendar day${i === 1 ? '' : 's'} earlier` : 'Current day', interval(result), fmt(models.distributedLag.thermalVifAfterMonth[i], 1)]).concat([['Lag 0–3 sum', interval(models.distributedLag.cumulative), '—']]), 'Simultaneous lag coefficients from the month + weather + thermal lags model. Correlated predictors can make individual lag coefficients unstable.');
  $('lag-finding').textContent = 'The lag 0–3 sum compares PM₂.₅ today under a 1°C higher thermal measure on each of four predictor days, holding model controls fixed. It is not a sum of pollution across four days. The previous-PM model conditions on pollution persistence and therefore asks a different question.';
  const sensitivity = chosen.map(([key, result, contrast]) => [modelNames[key], contrast, ...['3', '7', '14'].map(bandwidth => `${fmt(result.hacSensitivity[bandwidth][0])} to ${fmt(result.hacSensitivity[bandwidth][1])}`)]);
  table('model-sensitivity', ['Model', 'Contrast', 'HAC bandwidth 3 · 95% interval', 'Bandwidth 7', 'Bandwidth 14'], sensitivity, 'Bandwidth sensitivity changes the uncertainty estimate; coefficients and samples stay fixed.');
  const methods = $('extended-methods'); methods.replaceChildren();
  ['Every model has separate intercepts for the 12 months. Weather terms are linear wind, linear relative humidity and log-transformed daily precipitation. Thermal lag values refer to real calendar days; gaps are not bridged.', 'Intervals use a calendar-aware Bartlett Newey–West covariance, n/(n−p) correction and a normal 1.96 multiplier. They address serial dependence under this model; they do not remove confounding, measurement error or uncertainty from model selection.', `The common sample covers ${models.matchedFrom} through ${models.matchedThrough}, with ${models.monthlyMatchedDays.join(', ')} days in January through December. Seasonal smooths use all eligible daily pairs rather than this smaller lag-complete sample.`, metric === 'utci' ? 'UTCI includes wind and humidity. The weather-adjusted UTCI coefficient conditions on components already used to calculate the index; it does not estimate an overall effect of thermal stress.' : 'Weather adjustment describes the temperature association conditional on the included weather variables. Rain, wind and humidity may have nonlinear or lagged relationships beyond the main specification.'].forEach(text => methods.append(element('p', text)));
  if (models.weatherFormSensitivity) methods.append(element('p', `Allowing squared wind and humidity terms changes the same-day weather-adjusted estimate to ${interval(models.weatherFormSensitivity.current)} µg/m³ per °C, on the same sample.`));
  const summary = $('findings-summary'); summary.replaceChildren(element('p', `${city.city}: the within-month same-day estimate is ${fmt(models.monthOnly.current.estimate)} µg/m³ per °C before weather adjustment and ${fmt(models.weatherAdjusted.current.estimate)} after including wind, humidity and precipitation.`), element('p', `The adjusted same-day 95% interval is ${fmt(models.weatherAdjusted.current.ci95[0])} to ${fmt(models.weatherAdjusted.current.ci95[1])}. The lag 0–3 sum is ${interval(models.distributedLag.cumulative)}; after also conditioning on previous-day PM₂.₅, it is ${interval(models.priorPmSensitivity.cumulative)}.`), element('p', interpretation[city.id]));
}

export async function mountFindings(records) {
  const response = await fetch(new URL('./data/findings.json', import.meta.url));
  if (!response.ok) throw new Error(`findings.json (${response.status})`);
  const findings = await response.json();
  const params = new URLSearchParams(location.search);
  const state = {city: params.get('fCity') || params.get('city') || 'seoul', metric: params.get('fMetric') || params.get('metric') || 'temperature'};
  if (!findings.cities.some(city => city.id === state.city)) state.city = 'seoul';
  if (!['temperature', 'utci'].includes(state.metric)) state.metric = 'temperature';
  $('findings-city').replaceChildren(...findings.cities.map(city => element('option', city.city, {value: city.id})));
  $('findings-city').value = state.city; $('findings-metric').value = state.metric;
  let current, currentDays;
  const render = () => {
    state.city = $('findings-city').value; state.metric = $('findings-metric').value;
    const city = findings.cities.find(city => city.id === state.city), record = records.find(record => record.id === state.city);
    const {days} = dailyPairs(record.pmData, record.heatData, {heatMetric: state.metric, basis: 'local', utcOffsetMinutes: record.utcOffsetHours * 60, from: '2024-01-01', through: '2024-12-31'});
    drawSeasons(city, state.metric, days); renderModels(city, state.metric); current = {city, metric: state.metric}; currentDays = days;
  };
  const saveSelection = () => {
    const params = new URLSearchParams(location.search); params.set('fCity', state.city); params.set('fMetric', state.metric);
    history.replaceState(null, '', `${location.pathname}?${params}${location.hash}`);
  };
  for (const id of ['findings-city', 'findings-metric']) $(id).addEventListener('change', () => {
    render(); saveSelection();
  });
  $('download-findings').addEventListener('click', () => {
    const rows = [['city', 'metric', 'calendar', 'year', 'model', 'n_days', 'contrast', 'estimate_ug_m3_per_degree', 'hac7_se', 'hac7_ci_lower', 'hac7_ci_upper', 'partial_r_squared', 'residual_lag1_r']];
    for (const [key, model] of Object.entries(current.city.models[current.metric])) {
      if (!model?.current) continue;
      const entries = key === 'distributedLag' || key === 'priorPmSensitivity' ? [...model.lags.map((result, i) => [`lag${i}`, result]), ['lag0to3Sum', model.cumulative]] : [['current', model.current]];
      for (const [contrast, result] of entries) rows.push([current.city.id, current.metric, 'local-standard', 2024, key, model.n, contrast, result.estimate, result.standardError, ...result.ci95, model.partialR2, model.residualLag1]);
    }
    const cell = value => /[",\r\n]/.test(String(value)) ? `"${String(value).replaceAll('"', '""')}"` : String(value);
    const blob = new Blob(['\uFEFF', rows.map(row => row.map(cell).join(',')).join('\r\n')], {type: 'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob), link = element('a', undefined, {href: url, download: `air-heat-adjusted-${current.city.id}-${current.metric}-2024.csv`});
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('findings-download-status').textContent = 'Model estimates downloaded.';
  });
  let resize;
  window.addEventListener('resize', () => { clearTimeout(resize); resize = setTimeout(() => { if (current) { drawLags(current.city.models[current.metric].distributedLag, current.metric); drawSeasons(current.city, current.metric, currentDays); } }, 100); });
  $('findings-content').hidden = false; $('findings-status').textContent = '';
  render(); saveSelection();
}
