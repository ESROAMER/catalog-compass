'use strict';

const fields = [
  ['sku', 'SKU', 'The supplier’s product identifier'],
  ['name', 'Product name', 'A readable name for the item'],
  ['regular_price', 'Regular price', 'Standard selling price, not cost'],
  ['sale_price', 'Sale price', 'Optional discounted price'],
  ['currency', 'Currency', 'Explicit currency code, if supplied'],
  ['product_type', 'Product type', 'Simple, variable, variation, etc.'],
  ['parent_sku', 'Parent SKU', 'Links a variation to its parent'],
  ['barcode', 'Barcode / GTIN', 'EAN, UPC, or another barcode'],
  ['stock', 'Stock quantity', 'Available units, if supplied'],
  ['description', 'Description', 'Long-form product information'],
];
const requiredFields = ['sku', 'name', 'regular_price'];

const state = { step: 0, csv: '', filename: '', profile: null, mapping: {}, suggestions: [], mappingWarnings: [], manual: new Set(), engine: null, report: null, filter: 'all', busy: false, status: null, connection: {mode: 'local'} };
const $ = id => document.getElementById(id);
const text = (tag, content, className) => { const node = document.createElement(tag); node.textContent = content == null ? '' : String(content); if (className) node.className = className; return node; };

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.error || `Request failed (${response.status}). Please try again.`);
  }
  return response;
}

function notice(message, kind = '') {
  $('notice').textContent = message;
  $('notice').className = `notice ${kind}`;
  $('notice').hidden = !message;
}

const fieldLabel = field => fields.find(item => item[0] === field)?.[1] || field;

function conflictAction(selected, column) {
  if (selected.includes('sku') && selected.includes('barcode')) return `Use the supplier's internal item reference for SKU and the GTIN/EAN/UPC column for Barcode / GTIN. Use "${column}" only once. If no barcode column exists, leave Barcode / GTIN as Not provided.`;
  if (selected.includes('name') && selected.includes('description')) return 'Use the product title for Product name and a separate column of product text for Description. If no description column exists, leave Description as Not provided.';
  return `Keep "${column}" for the correct field. Choose another column for the other field, or select Not provided if optional.`;
}

function currentColumnConflicts() {
  const columns = new Map();
  Object.entries(state.mapping).forEach(([field, column]) => {
    if (column) columns.set(column, [...(columns.get(column) || []), field]);
  });
  return Array.from(columns).filter(([, selected]) => selected.length > 1);
}

function renderMappingWarnings() {
  const conflicts = currentColumnConflicts();
  const warnings = state.mappingWarnings.filter(warning => {
    if (typeof warning === 'string') return true;
    const related = warning.fields || [];
    // A user decision can keep one optional field unselected. Required fields
    // must still have a column, and an active collision is always shown below.
    const reviewed = related.some(field => state.manual.has(field));
    const missingRequired = related.some(field => requiredFields.includes(field) && !state.mapping[field]);
    return (!reviewed || missingRequired) && !conflicts.some(([column]) => column === warning.column);
  }).map(warning => typeof warning === 'string' ? {message: warning, fields: []} : warning);
  conflicts.forEach(([column, selected]) => warnings.push({
    fields: selected,
    message: `Column "${column}" is selected for ${selected.map(fieldLabel).join(' and ')}. One column can only serve one field.`,
    action: conflictAction(selected, column),
  }));
  const container = $('mapping-warnings');
  container.replaceChildren(); container.hidden = !warnings.length;
  document.querySelectorAll('.mapping-select').forEach(select => {
    select.classList.remove('needs-review'); select.removeAttribute('aria-describedby');
  });
  warnings.forEach((warning, index) => {
    const card = text('div', '', 'mapping-warning'); card.id = `mapping-warning-${index}`;
    card.append(text('strong', warning.message));
    if (warning.action) card.append(text('p', warning.action));
    const actions = text('div', '', 'warning-actions');
    (warning.fields || []).forEach(field => {
      const select = $(`mapping-${field}`);
      if (!select) return;
      select.classList.add('needs-review');
      select.setAttribute('aria-describedby', `${select.getAttribute('aria-describedby') || ''} ${card.id}`.trim());
      const button = text('button', `Review ${fieldLabel(field)}`, 'text-button'); button.type = 'button'; button.disabled = state.busy;
      button.addEventListener('click', () => {
        if (!requiredFields.includes(field)) $('optional-fields').open = true;
        select.focus({preventScroll: true}); select.scrollIntoView({behavior: 'smooth', block: 'center'});
      });
      actions.append(button);
    });
    card.append(actions); container.append(card);
  });
}

function refreshControls() {
  document.querySelectorAll('[data-step]').forEach(button => {
    const step = Number(button.dataset.step);
    button.disabled = state.busy || (step === 1 && !state.profile) || (step === 2 && !state.report);
    button.classList.toggle('active', step === state.step);
    button.classList.toggle('complete', (step === 0 && !!state.profile) || (step === 1 && !!state.report));
    if (step === state.step) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current');
  });
  document.querySelectorAll('.sample-button, .mapping-select, #file-input, #change-file, #edit-mapping, #confirm-mapping, #suggest-button, #export-issues, #export-normalized').forEach(button => button.disabled = state.busy);
  const missing = requiredFields.filter(field => !state.mapping[field]);
  const mapped = Object.values(state.mapping).filter(Boolean);
  const duplicate = new Set(mapped).size !== mapped.length;
  $('check-button').disabled = state.busy || !$('confirm-mapping').checked || missing.length > 0 || duplicate;
  const conflict = currentColumnConflicts()[0];
  $('confirmation-help').textContent = conflict ? `"${conflict[0]}" is selected for ${conflict[1].map(fieldLabel).join(' and ')}. Use it only once.` : missing.length ? `Select columns for ${missing.map(fieldLabel).join(', ')} to continue.` : 'Only selected fields will be checked.';
  renderMappingWarnings();
  document.body.classList.toggle('busy', state.busy);
  $('drop-zone').setAttribute('aria-disabled', String(state.busy));
  renderConnection();
}

function apiHost(base) {
  try { return new URL(base).host || 'your selected service'; }
  catch { return 'your selected service'; }
}

function settingsFeedback(message, error = false) {
  $('settings-feedback').textContent = message;
  $('settings-feedback').hidden = !message;
  $('settings-feedback').classList.toggle('error', error);
}

function renderConnection() {
  const remote = state.connection.mode === 'api';
  const ready = remote || !!state.status?.model?.ready;
  $('model-status').classList.toggle('ready', ready);
  $('model-status').classList.toggle('offline', !ready);
  $('model-status-text').textContent = remote ? 'API service selected' : ready ? 'Local AI ready' : 'Local AI offline';
  $('model-status').title = remote ? `${state.connection.model} · ${apiHost(state.connection.base_url)}` : state.status?.model?.message || '';
  $('inference-destination').textContent = remote ? `AI suggestions send column names and up to 3 short sample values per column to ${apiHost(state.connection.base_url)}. The full CSV stays on this computer.` : 'Local mode: column samples stay on this computer.';
  $('privacy-summary').textContent = remote ? `API mode: column samples go to ${apiHost(state.connection.base_url)}. Your source file stays unchanged.` : 'Local mode: your data stays on this computer. Your source file stays unchanged.';
  const apiSelected = $('source-api').checked;
  $('local-settings').hidden = apiSelected; $('api-settings').hidden = !apiSelected;
  const runtime = state.status?.runtime || {};
  $('local-setup-status').textContent = runtime.busy || runtime.phase === 'error' ? runtime.message : state.status?.model?.ready ? 'Local AI is ready. Choose Use local model to keep all samples on this computer.' : runtime.installed ? 'Model files are installed. Click Start local AI.' : 'The model is not installed. Use the setup button below, or choose API service.';
  $('start-local-model').textContent = runtime.busy ? (runtime.phase === 'downloading' ? 'Downloading…' : 'Starting…') : runtime.installed ? 'Start local AI' : 'Set up & start local AI (~672 MB)';
  $('start-local-model').disabled = state.busy || !!runtime.busy || runtime.supported === false || !!state.status?.model?.ready;
  document.querySelectorAll('#ai-settings input, #ai-settings select, #use-local-model, #test-use-api, #forget-api, #check-local-model, #open-ai-settings').forEach(input => input.disabled = state.busy);
  $('api-consent-label').textContent = `Allow column names and up to 3 short sample values per column to be sent to ${apiHost($('api-base-url').value)} when I request AI suggestions.`;
}

async function refreshLocalStatus() {
  state.status = await (await api('/api/status')).json();
  renderConnection(); renderEngine();
}

let localPollTimer = null;
function followLocalStartup() {
  if (localPollTimer !== null) return;
  localPollTimer = setTimeout(async () => {
    localPollTimer = null;
    try {
      await refreshLocalStatus();
      if (state.status?.runtime?.busy) followLocalStartup();
    } catch { settingsFeedback('Could not refresh local setup status. Check that the app is still running.', true); }
  }, 1800);
}

function openSettings() {
  $('source-local').checked = state.connection.mode === 'local';
  $('source-api').checked = state.connection.mode === 'api';
  settingsFeedback(''); renderConnection(); $('ai-settings').showModal();
}

async function settingsAction(button, label, action) {
  settingsFeedback('');
  await perform(button, label, async () => {
    try { await action(); }
    catch (error) { settingsFeedback(error.message || 'Connection failed.', true); }
  });
}

async function perform(button, loading, action) {
  if (state.busy) return;
  const original = button ? Array.from(button.childNodes) : [];
  state.busy = true;
  notice('');
  refreshControls();
  if (button) button.textContent = loading;
  try { await action(); }
  catch (error) { notice(error.message || 'Something went wrong. Please try again.', 'error'); }
  finally { state.busy = false; if (button) button.replaceChildren(...original); refreshControls(); }
}

function setStep(step) {
  notice('');
  state.step = step;
  document.querySelectorAll('.stage').forEach((section, index) => section.hidden = index !== step);
  refreshControls();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderPreview() {
  const { headers, preview, row_count } = state.profile;
  document.querySelectorAll('.source-name').forEach(node => node.textContent = state.filename);
  document.querySelectorAll('.source-detail').forEach(node => node.textContent = `${row_count.toLocaleString()} rows · ${headers.length} columns`);
  $('preview-caption').textContent = `First ${Math.min(preview.length, 5)} rows`;
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const tr = document.createElement('tr');
  tr.append(text('th', 'ROW', 'row-number'));
  headers.forEach(header => tr.append(text('th', header)));
  head.append(tr); table.append(head);
  const body = document.createElement('tbody');
  preview.slice(0, 5).forEach((record, index) => {
    const row = document.createElement('tr');
    row.append(text('td', index + 2, 'row-number'));
    headers.forEach(header => { const cell = text('td', record[header] || '—'); cell.title = String(record[header] ?? ''); row.append(cell); });
    body.append(row);
  });
  table.append(body); $('preview-table').replaceChildren(table);
}

function renderEngine() {
  $('engine-banner').title = '';
  if (state.engine) {
    const isModel = ['open_model', 'api_model'].includes(state.engine.kind);
    const origin = state.engine.kind === 'api_model' ? `API: ${state.engine.name}` : 'Local AI';
    $('engine-title').textContent = isModel ? `${origin} suggestions ready — review the selections` : 'Column suggestions ready';
    const elapsed = Number.isFinite(state.engine.elapsed_ms) ? ` Took ${(state.engine.elapsed_ms / 1000).toFixed(1)} s.` : '';
    $('engine-description').textContent = (isModel ? 'Review any flagged selections and check the example values. AI suggestions can still be wrong.' : 'Review the suggested columns against the example values.') + elapsed;
    $('engine-banner').title = isModel ? `Model: ${state.engine.name}` : '';
  } else if (state.connection.mode === 'local' && state.status?.model && !state.status.model.ready) {
    $('engine-title').textContent = 'Local AI is offline';
    $('engine-description').textContent = 'Open AI settings to start it or connect an API service. You can also select columns yourself.';
  } else {
    $('engine-title').textContent = 'Choose columns yourself or use AI';
    $('engine-description').textContent = 'Check each selection against the example values.';
  }
}

function renderMapping() {
  const container = $('mapping-fields'); container.replaceChildren();
  const optional = $('optional-mapping-fields'); optional.replaceChildren();
  fields.forEach(([field, label, description]) => {
    const required = requiredFields.includes(field);
    const row = text('div', '', 'mapping-row');
    const fieldInfo = document.createElement('div');
    const name = text('label', label, 'field-title'); name.htmlFor = `mapping-${field}`;
    fieldInfo.append(name, text('span', description, 'field-description'));
    const select = document.createElement('select'); select.id = `mapping-${field}`; select.className = 'mapping-select';
    const empty = text('option', required ? 'Choose a column' : 'Not provided'); empty.value = ''; select.append(empty);
    state.profile.headers.forEach(header => { const option = text('option', header); option.value = header; select.append(option); });
    select.value = state.mapping[field] || ''; select.classList.toggle('unmapped', !select.value);
    const note = text('div', '', 'mapping-note');
    const values = state.profile.column_samples?.[select.value] || [];
    note.append(text('span', select.value ? (values.length ? values.slice(0, 2).map(value => String(value).length > 65 ? String(value).slice(0, 65) + '…' : value).join(' · ') : 'All sampled cells are blank') : (required ? 'Select a column to see its values' : 'This field will not be checked')));
    if (state.manual.has(field)) note.append(text('small', 'Your selection'));
    else if (state.engine && select.value) note.append(text('small', ['open_model', 'api_model'].includes(state.engine.kind) ? 'AI suggestion' : 'Suggested match'));
    select.addEventListener('change', () => {
      state.mapping[field] = select.value || null;
      state.manual.add(field); state.report = null;
      $('confirm-mapping').checked = false;
      renderMapping(); refreshControls(); $(`mapping-${field}`).focus();
    });
    row.append(fieldInfo, select, note); (required ? container : optional).append(row);
  });
  const selectedOptional = fields.filter(([field]) => !requiredFields.includes(field) && state.mapping[field]).length;
  $('optional-count').textContent = `(${selectedOptional} of 7 selected)`;
  $('type-assumption').hidden = !!state.mapping.product_type;
  renderEngine();
}

async function loadCsv(csv, filename) {
  const profile = await (await api('/api/profile', { csv })).json();
  state.csv = csv; state.filename = filename; state.profile = profile;
  state.mapping = {}; state.suggestions = []; state.mappingWarnings = []; state.manual = new Set(); state.engine = null; state.report = null;
  $('confirm-mapping').checked = false; $('mapping-warnings').hidden = true;
  $('optional-fields').open = false;
  renderPreview(); renderMapping(); setStep(1);
}

async function readFile(file) {
  if (!/\.csv$/i.test(file.name)) throw new Error('Please choose a CSV file.');
  if (file.size > 2 * 1024 * 1024) throw new Error('This prototype supports CSV files smaller than 2 MB.');
  let csv;
  try { csv = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer()); }
  catch { throw new Error('This file is not valid UTF-8. Save it as UTF-8 CSV and try again.'); }
  await loadCsv(csv, file.name);
}

function renderReport() {
  const { summary, issues } = state.report;
  $('metric-total').textContent = summary.total_rows.toLocaleString();
  $('metric-errors').textContent = summary.error_count.toLocaleString();
  $('metric-warnings').textContent = summary.warning_count.toLocaleString();
  $('metric-affected').textContent = summary.affected_rows.toLocaleString();
  const notes = state.report.notes || [];
  $('review-assumptions').hidden = !notes.length;
  $('report-notes').replaceChildren(...notes.map(note => text('li', note)));
  const filtered = issues.filter(issue => state.filter === 'all' || issue.severity === state.filter);
  $('findings-count').textContent = filtered.length;
  $('empty-findings').hidden = filtered.length > 0;
  $('findings-table').hidden = !filtered.length;
  $('empty-description').textContent = issues.length ? 'No issues match this filter.' : 'No issues found in the selected fields. Other fields were not checked.';
  const table = document.createElement('table');
  const head = document.createElement('thead'); const heading = document.createElement('tr');
  ['Row', 'SKU', 'Level', 'Issue'].forEach(label => heading.append(text('th', label))); head.append(heading); table.append(head);
  const body = document.createElement('tbody');
  filtered.forEach(issue => {
    const row = document.createElement('tr');
    row.append(text('td', issue.row ?? '—', 'row-number'), text('td', issue.sku || '—', 'issue-sku'));
    const level = document.createElement('td'); level.append(text('span', issue.severity === 'error' ? 'Error' : 'Warning', `severity-pill ${issue.severity}`)); row.append(level);
    const message = text('td', '', 'message-cell');
    message.append(text('span', String(issue.code || issue.field || 'Review').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase()), 'issue-code'), text('span', issue.message));
    if (issue.value !== undefined && issue.value !== null && issue.value !== '') message.append(text('span', `Source value: ${typeof issue.value === 'object' ? JSON.stringify(issue.value) : issue.value}`, 'issue-value'));
    row.append(message); body.append(row);
  });
  table.append(body); $('findings-table').replaceChildren(table);
  document.querySelectorAll('[data-filter]').forEach(button => { const active = button.dataset.filter === state.filter; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); });
}

async function exportCsv(kind, button) {
  await perform(button, 'Preparing CSV…', async () => {
    const response = await api('/api/export', { csv: state.csv, mapping: state.mapping, options: {}, kind });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url;
    const disposition = response.headers.get('Content-Disposition') || '';
    const suppliedName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
    link.download = suppliedName || `${state.filename.replace(/\.csv$/i, '')}-${kind}.csv`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice(`${kind === 'issues' ? 'Issue report' : 'Mapped CSV'} downloaded. In Excel, import SKU and barcode columns as text to keep leading zeros.`, 'success');
  });
}

document.querySelectorAll('[data-step]').forEach(button => button.addEventListener('click', () => setStep(Number(button.dataset.step))));
$('change-file').addEventListener('click', () => { notice(''); setStep(0); });
$('edit-mapping').addEventListener('click', () => { notice(''); setStep(1); });
$('confirm-mapping').addEventListener('change', refreshControls);
$('file-input').addEventListener('change', event => {
  const file = event.target.files[0];
  if (file) perform(null, '', async () => { await readFile(file); });
  event.target.value = '';
});
['dragenter', 'dragover'].forEach(name => $('drop-zone').addEventListener(name, event => { event.preventDefault(); if (!state.busy) $('drop-zone').classList.add('dragover'); }));
['dragleave', 'drop'].forEach(name => $('drop-zone').addEventListener(name, event => { event.preventDefault(); $('drop-zone').classList.remove('dragover'); }));
$('drop-zone').addEventListener('drop', event => {
  if (state.busy) return;
  const file = event.dataTransfer.files[0];
  if (!file) return;
  if (!/\.csv$/i.test(file.name)) return notice('Please choose a CSV file.', 'error');
  perform(null, '', async () => { await readFile(file); });
});
$('suggest-button').addEventListener('click', event => perform(event.currentTarget, 'Matching columns…', async () => {
  if (state.connection.mode === 'local' && !state.status?.model?.ready) {
    openSettings(); settingsFeedback('Start local AI or choose API service to get suggestions.'); return;
  }
  const result = await (await api('/api/map', { csv: state.csv, connection: state.connection })).json();
  state.mapping = result.mapping || {}; state.suggestions = result.suggestions || []; state.engine = result.engine; state.manual = new Set(); state.report = null;
  $('confirm-mapping').checked = false;
  state.mappingWarnings = result.warnings || [];
  renderMapping();
  $('optional-fields').open = true;
}));
$('check-button').addEventListener('click', event => perform(event.currentTarget, 'Checking…', async () => {
  state.report = await (await api('/api/check', { csv: state.csv, mapping: state.mapping, options: {} })).json();
  state.filter = 'all'; renderReport(); setStep(2);
}));
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => { state.filter = button.dataset.filter; renderReport(); }));
$('export-issues').addEventListener('click', event => exportCsv('issues', event.currentTarget));
$('export-normalized').addEventListener('click', event => exportCsv('normalized', event.currentTarget));

$('open-ai-settings').addEventListener('click', openSettings);
$('close-ai-settings').addEventListener('click', () => $('ai-settings').close());
document.querySelectorAll('[name="ai-source"]').forEach(input => input.addEventListener('change', () => { settingsFeedback(''); renderConnection(); }));
$('api-preset').addEventListener('change', () => {
  const presets = {deepseek: ['https://api.deepseek.com', 'deepseek-flash'], openrouter: ['https://openrouter.ai/api/v1', '']};
  const preset = presets[$('api-preset').value];
  if (preset) { $('api-base-url').value = preset[0]; $('api-model').value = preset[1]; }
  $('api-key').value = ''; $('api-consent').checked = false; settingsFeedback(''); renderConnection();
});
['api-base-url', 'api-model', 'api-key', 'api-format'].forEach(id => $(id).addEventListener('input', () => {
  $('api-consent').checked = false; settingsFeedback(''); renderConnection();
}));
$('test-use-api').addEventListener('click', event => settingsAction(event.currentTarget, 'Testing…', async () => {
  if (!$('api-consent').checked) throw new Error('Confirm where column samples will be sent before using this API.');
  const connection = {mode: 'api', base_url: $('api-base-url').value.trim().replace(/\/+$/, '').replace(/\/chat\/completions$/, ''), model: $('api-model').value.trim(), api_key: $('api-key').value.trim(), format: $('api-format').value};
  const result = await (await api('/api/model/test', {connection})).json();
  state.connection = connection;
  settingsFeedback(`API selected: ${result.engine.name}. ${result.message}`);
  renderEngine();
}));
$('use-local-model').addEventListener('click', () => {
  state.connection = {mode: 'local'}; renderConnection(); renderEngine(); $('ai-settings').close();
});
$('forget-api').addEventListener('click', () => {
  ['api-base-url', 'api-model', 'api-key'].forEach(id => $(id).value = '');
  $('api-preset').value = 'custom'; $('api-format').value = 'json'; $('api-consent').checked = false;
  state.connection = {mode: 'local'};
  renderConnection(); renderEngine(); settingsFeedback('API settings cleared. Local mode is selected.');
});
$('check-local-model').addEventListener('click', event => settingsAction(event.currentTarget, 'Checking…', refreshLocalStatus));
$('start-local-model').addEventListener('click', event => settingsAction(event.currentTarget, 'Starting…', async () => {
  state.status ||= {};
  state.status.runtime = await (await api('/api/model/start', {install: !state.status?.runtime?.installed, cpu: $('local-cpu').checked})).json();
  state.connection = {mode: 'local'}; followLocalStartup(); renderEngine();
}));

async function initialize() {
  try {
    state.status = await (await api('/api/status')).json();
    const { model, samples } = state.status;
    $('model-status').classList.add(model.ready ? 'ready' : 'offline');
    $('model-status-text').textContent = model.ready ? 'Local AI ready' : 'AI offline · manual matching available';
    $('model-status').title = `${model.name} · ${model.message || model.backend || ''}`;
    $('footer-model').textContent = '';
    if (state.status.runtime?.busy) followLocalStartup();
    $('featured-sample').replaceChildren();
    $('sample-list').replaceChildren();
    (samples || []).forEach(sample => {
      const button = text('button', '', 'sample-button'); button.type = 'button';
      const featured = sample.id === 'supplier-demo';
      button.append(text('strong', featured ? 'Load sample with errors' : sample.name), text('p', featured ? '10 fictional products with missing prices, duplicate SKUs and conflicts.' : sample.description));
      button.addEventListener('click', () => perform(button, 'Opening sample…', async () => {
        const result = await (await api(`/api/samples/${encodeURIComponent(sample.id)}`)).json();
        await loadCsv(result.csv, result.filename);
      }));
      $(featured ? 'featured-sample' : 'sample-list').append(button);
    });
    $('more-samples').hidden = !(samples || []).some(sample => sample.id !== 'supplier-demo');
    if (!(samples || []).length) $('featured-sample').append(text('p', 'No samples available. Upload a CSV to begin.', 'secondary'));
    renderEngine();
  } catch (error) {
    $('model-status-text').textContent = 'Connection unavailable';
    $('featured-sample').replaceChildren(text('p', 'Could not load samples. Check the local server and refresh this page.', 'secondary'));
    notice(error.message, 'error');
  }
  refreshControls();
}

initialize();
