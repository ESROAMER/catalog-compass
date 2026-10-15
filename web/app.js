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

const state = { step: 0, csv: '', filename: '', profile: null, mapping: {}, suggestions: [], manual: new Set(), engine: null, report: null, filter: 'all', busy: false, status: null };
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

function refreshControls() {
  document.querySelectorAll('[data-step]').forEach(button => {
    const step = Number(button.dataset.step);
    button.disabled = state.busy || (step === 1 && !state.profile) || (step === 2 && !state.report);
    button.classList.toggle('active', step === state.step);
    button.classList.toggle('complete', (step === 0 && !!state.profile) || (step === 1 && !!state.report));
    if (step === state.step) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current');
  });
  document.querySelectorAll('.sample-button, .mapping-select, #file-input, #change-file, #edit-mapping, #confirm-mapping, #suggest-button, #export-issues, #export-normalized').forEach(button => button.disabled = state.busy);
  const missing = ['sku', 'name', 'regular_price'].filter(field => !state.mapping[field]);
  const mapped = Object.values(state.mapping).filter(Boolean);
  const duplicate = new Set(mapped).size !== mapped.length;
  $('check-button').disabled = state.busy || !$('confirm-mapping').checked || missing.length > 0 || duplicate;
  $('confirmation-help').textContent = missing.length ? `Map ${missing.map(field => fields.find(item => item[0] === field)[1]).join(', ')} to enable checking.` : duplicate ? 'Each source column can be mapped only once. Review the repeated selections.' : 'Unmapped source columns are omitted. Mapped values are never guessed or filled in.';
  document.body.classList.toggle('busy', state.busy);
  $('drop-zone').setAttribute('aria-disabled', String(state.busy));
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
  document.querySelectorAll('.source-detail').forEach(node => node.textContent = `${row_count.toLocaleString()} records · ${headers.length} source columns · Original values preserved`);
  $('preview-caption').textContent = `First ${Math.min(preview.length, 5)} of ${row_count.toLocaleString()} records`;
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
  if (state.engine) {
    const isModel = state.engine.kind === 'open_model';
    $('engine-title').textContent = isModel ? `Open-model suggestions · ${state.engine.name}` : `Rule-based suggestions · ${state.engine.name || 'Header matching'}`;
    const elapsed = Number.isFinite(state.engine.elapsed_ms) ? ` Completed in ${(state.engine.elapsed_ms / 1000).toFixed(1)}s.` : '';
    $('engine-description').textContent = (isModel ? 'The model proposed the mappings below. Check the source preview and adjust anything that needs context.' : 'These are deterministic header matches, not AI output. Review the proposed fields or select columns manually.') + elapsed;
  } else if (state.status?.model && !state.status.model.ready) {
    $('engine-title').textContent = 'Open model unavailable · Manual mapping is available';
    $('engine-description').textContent = `${state.status.model.message || 'The configured model is not connected.'} You can select each source column yourself.`;
  } else {
    $('engine-title').textContent = 'Your review, assisted by an open model';
    $('engine-description').textContent = 'Choose “Suggest field mappings” to analyze the headers and sample values. You can also map the fields manually.';
  }
}

function renderMapping() {
  const container = $('mapping-fields'); container.replaceChildren();
  fields.forEach(([field, label, description]) => {
    const row = text('div', '', 'mapping-row');
    const fieldInfo = document.createElement('div');
    const name = text('label', label + (['sku', 'name', 'regular_price'].includes(field) ? ' *' : ''), 'field-title'); name.htmlFor = `mapping-${field}`;
    fieldInfo.append(name, text('span', description, 'field-description'));
    const select = document.createElement('select'); select.id = `mapping-${field}`; select.className = 'mapping-select';
    const empty = text('option', 'Not mapped'); empty.value = ''; select.append(empty);
    state.profile.headers.forEach(header => { const option = text('option', header); option.value = header; select.append(option); });
    select.value = state.mapping[field] || ''; select.classList.toggle('unmapped', !select.value);
    const note = text('div', '', 'mapping-note');
    const suggestion = state.suggestions.find(item => item.field === field);
    if (state.manual.has(field)) note.append(text('span', 'YOUR SELECTION', 'manual-note'));
    note.append(text('span', suggestion?.reason || (select.value ? 'Review this field against the source values.' : 'Select a source column, or leave this field out.')));
    select.addEventListener('change', () => {
      state.mapping[field] = select.value || null;
      state.manual.add(field); state.report = null;
      $('confirm-mapping').checked = false;
      renderMapping(); refreshControls(); $(`mapping-${field}`).focus();
    });
    row.append(fieldInfo, select, note); container.append(row);
  });
  renderEngine();
}

async function loadCsv(csv, filename) {
  const profile = await (await api('/api/profile', { csv })).json();
  state.csv = csv; state.filename = filename; state.profile = profile;
  state.mapping = {}; state.suggestions = []; state.manual = new Set(); state.engine = null; state.report = null;
  $('confirm-mapping').checked = false; $('mapping-warnings').hidden = true;
  renderPreview(); renderMapping(); setStep(1);
  notice(`${filename} is ready. Suggest or select the field mappings, then confirm them to run the checks.`, 'success');
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
  $('empty-description').textContent = issues.length ? 'There are no findings matching this filter. Choose another view to see the rest.' : 'The checks did not find any issues in the mapped fields. Unmapped fields were not checked.';
  const table = document.createElement('table');
  const head = document.createElement('thead'); const heading = document.createElement('tr');
  ['ROW', 'SKU', 'LEVEL', 'FINDING'].forEach(label => heading.append(text('th', label))); head.append(heading); table.append(head);
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
    notice(`${kind === 'issues' ? 'Findings report' : 'Normalized catalog'} downloaded. Formula-like text is escaped; import SKU and barcode columns as text to retain leading zeros.`, 'success');
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
$('suggest-button').addEventListener('click', event => perform(event.currentTarget, 'Reading the fields…', async () => {
  const result = await (await api('/api/map', { csv: state.csv })).json();
  state.mapping = result.mapping || {}; state.suggestions = result.suggestions || []; state.engine = result.engine; state.manual = new Set(); state.report = null;
  $('confirm-mapping').checked = false;
  $('mapping-warnings').replaceChildren(...(result.warnings || []).map(warning => text('p', typeof warning === 'string' ? warning : JSON.stringify(warning))));
  $('mapping-warnings').hidden = !(result.warnings || []).length;
  renderMapping();
  notice(state.engine?.kind === 'open_model' ? 'Model suggestions are ready. Review the mappings before running the checks.' : 'Rule-based suggestions are ready. These were not generated by an AI model.', 'success');
}));
$('check-button').addEventListener('click', event => perform(event.currentTarget, 'Checking the catalog…', async () => {
  state.report = await (await api('/api/check', { csv: state.csv, mapping: state.mapping, options: {} })).json();
  state.filter = 'all'; renderReport(); setStep(2);
  notice(`Review complete: ${state.report.summary.error_count} errors and ${state.report.summary.warning_count} warnings.`, 'success');
}));
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => { state.filter = button.dataset.filter; renderReport(); }));
$('export-issues').addEventListener('click', event => exportCsv('issues', event.currentTarget));
$('export-normalized').addEventListener('click', event => exportCsv('normalized', event.currentTarget));

async function initialize() {
  try {
    state.status = await (await api('/api/status')).json();
    const { model, samples } = state.status;
    $('model-status').classList.add(model.ready ? 'ready' : 'offline');
    $('model-status-text').textContent = model.ready ? `${model.name} · connected` : 'Model offline · manual review available';
    $('model-status').title = model.message || model.backend || '';
    $('footer-model').textContent = model.ready ? `${model.backend} · ${model.name}` : 'Local catalog review';
    $('sample-list').replaceChildren();
    (samples || []).forEach((sample, index) => {
      const button = text('button', '', 'sample-button'); button.type = 'button';
      button.append(text('span', `SAMPLE ${String(index + 1).padStart(2, '0')}`, 'sample-index'), text('strong', sample.name), text('p', sample.description), text('span', '↗', 'sample-arrow'));
      button.addEventListener('click', () => perform(button, 'Opening sample…', async () => {
        const result = await (await api(`/api/samples/${encodeURIComponent(sample.id)}`)).json();
        await loadCsv(result.csv, result.filename);
      }));
      $('sample-list').append(button);
    });
    if (!(samples || []).length) $('sample-list').append(text('div', 'No bundled samples are available. Choose your own CSV to begin.', 'sample-placeholder'));
    renderEngine();
  } catch (error) {
    $('model-status-text').textContent = 'Connection unavailable';
    $('sample-list').replaceChildren(text('div', 'Sample catalogs could not be loaded. Check that the local server is running, then refresh this page.', 'sample-placeholder'));
    notice(error.message, 'error');
  }
  refreshControls();
}

initialize();
