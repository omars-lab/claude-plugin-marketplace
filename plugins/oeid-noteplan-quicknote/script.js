/* global DataStore, Editor, CommandBar */
// oeid.noteplan-quicknote — /plan /meeting /note
// Workstreams/activities are discovered at runtime from DataStore.folders.
// Adding a new workstream folder surfaces it automatically — no code change needed.

// ─── Static config ────────────────────────────────────────────────────────────

const DOMAIN_LABELS = ['Work', 'Personal', 'NaqshCoffee', 'EarlBear']
const NOTE_DOMAIN_LABELS = ['Work', 'Personal', 'NaqshCoffee', 'EarlBear']

const PLAN_ROOTS = {
  work:     '🏢 ServiceNow/📆 Plans',
  personal: '🏡 Personal/🏡📆 Plans/Present',
  coffee:   '☕️ NaqshCoffee/📆 Plans',
  earlbear: '👥 EarlBear/📆 Plans',
}

const MEETING_FOLDERS = {
  work:     '🏢 ServiceNow/👤 Meetings',
  personal: '🏡 Personal/🏡👥 Meetings',
  coffee:   '☕️ NaqshCoffee/☕️👤 Meetings',
  earlbear: '👥 EarlBear/👥 Meetings',
}

const NOTE_FOLDERS = {
  work:     '🏢 ServiceNow/📝 Notes',
  personal: '🏡 Personal/🏡📝 Notes',
  coffee:   '☕️ NaqshCoffee/📝 Notes',
  earlbear: '👥 EarlBear/📝 Notes',
}

const DOMAIN_EMOJIS = {
  work: '🏢', personal: '🏡', coffee: '☕️', earlbear: '👥',
}

const NAMESPACE = {
  work: '🏢', personal: '🏡', coffee: '☕️', earlbear: '👥',
}

const STATUS_OPTIONS = [
  '🔮 Future', '🚦 Ready', '🟢 Started', '🟡 Paused', '🔴 Blocked', '❎ Canceled', '✅ Done',
]

const DAYS_AGO_OPTIONS = ['0', '1', '3', '7', '14', '30']

// Project subfolders under 🧑🏻‍💻 Development (Work or EarlBear)
const DEV_PROJECT_OPTIONS = ['— none —', '🤖 Config Agent', '💡 esgenius', '⚗️ Experiments', '🔧 Setup']

// Pre-fill suggestions for the title text prompt.
// Meeting: pre-fills based on domain convention (user edits from there).
// Plan: pre-fills based on workstream — leaves a useful starting point.
const MEETING_TITLE_PREFILL = {
  work:     '1-1 ',
  personal: '',
  coffee:   '',
  earlbear: '1-1 ',
}

const PLAN_TITLE_PREFILL = {
  '🏁': 'Onboarding ',
  '🎯': 'Impact ',
  '✍🏻': 'Documenting ',
}

// Static workstream labels for domains that have no subfolder structure.
// Used for filename emoji only — these never become folder paths.
const STATIC_WORKSTREAMS = {
  coffee:   ['🎨 Design', '🏪 Site', '👨🏻‍💼 Strategy', '🖼️ Vision'],
  earlbear: ['🧑🏻‍💻 Development', '👨🏻‍💼 Strategy'],
}

// Domains where workstream is a subfolder path (vs filename-only)
const WORKSTREAM_IS_FOLDER = { work: true, personal: true }

// ─── Helpers ──────────────────────────────────────────────────────────────────

function domainKey(label) {
  const map = { Work: 'work', Personal: 'personal', NaqshCoffee: 'coffee', EarlBear: 'earlbear' }
  return map[label]
}

function formatDate(daysAgo, fmt) {
  const d = new Date()
  d.setDate(d.getDate() - Number(daysAgo || 0))
  if (fmt === 'yymmdd') {
    const yy = String(d.getFullYear()).slice(2)
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${yy}${mm}${dd}`
  }
  if (fmt === 'iso') return d.toISOString().slice(0, 10)
  if (fmt === 'week') {
    const jan4 = new Date(d.getFullYear(), 0, 4)
    const start = new Date(jan4)
    start.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7))
    const wk = Math.floor((d - start) / (7 * 864e5)) + 1
    return `${d.getFullYear()}-W${String(wk).padStart(2, '0')}`
  }
  return ''
}

// Discover immediate subdirectories of a plan root via DataStore.folders.
// Falls back to STATIC_WORKSTREAMS for domains that have no subfolder structure
// (coffee, earlbear) — these provide the filename emoji only, not a folder path.
function getWorkstreams(domain) {
  const root = PLAN_ROOTS[domain]
  if (!root) return []
  const prefix = root + '/'
  const discovered = DataStore.folders
    .filter(f => f.startsWith(prefix) && !f.slice(prefix.length).includes('/'))
    .map(f => f.slice(prefix.length))
    .sort()
  return discovered.length ? discovered : (STATIC_WORKSTREAMS[domain] || [])
}

async function pick(options, placeholder) {
  const result = await CommandBar.showOptions(options, placeholder)
  return result ? result.value : null
}

async function getText(placeholder, defaultValue = '') {
  const result = await CommandBar.textPrompt('', placeholder, defaultValue)
  return (result && result.trim()) ? result.trim() : null
}

async function createAndOpen(title, folder, content) {
  const filename = DataStore.newNote(title, folder)
  if (!filename) {
    await CommandBar.prompt(`Could not create note "${title}"`, `Folder: ${folder}`, ['OK'])
    return
  }
  await Editor.openNoteByFilename(filename)
  Editor.content = content
}

// ─── Template builders ────────────────────────────────────────────────────────

function planBody(title, frontmatter, daysAgo) {
  const week = formatDate(daysAgo, 'week')
  return `${frontmatter}
# ${title}
* [ ] Is [[${title}]] done? >${week}
* [ ]
`
}

function meetingBody(title, frontmatter, daysAgo, isWork) {
  const week = formatDate(daysAgo, 'week')
  const base = `${frontmatter}
# ${title}
* [ ] Are Action Items for [[${title}]] done? >${week}
`
  if (isWork) {
    return base + `
## Attendees

## Agenda

## Notes

## Action Items
`
  }
  return base + `
## Notes

## Action Items
`
}

function noteBody(title, namespace) {
  return `---
doctype: 📝
started: ${formatDate(0, 'iso')}
namespace: ${namespace}
---
# ${title}
`
}

function workPlanFrontmatter(wsEmoji, statusEmoji, daysAgo) {
  return `---
doctype: 📆
status: ${statusEmoji}
started: ${formatDate(daysAgo, 'iso')}
namespace: 🏢
workstream: ${wsEmoji}
initiative:
---`
}

function personalPlanFrontmatter(actEmoji, statusEmoji, daysAgo) {
  return `---
doctype: 📆
status: ${statusEmoji}
started: ${formatDate(daysAgo, 'iso')}
namespace: 🏡
plantype: ${actEmoji}
initiative:
---`
}

function domainPlanFrontmatter(ns, wsEmoji, statusEmoji, daysAgo) {
  return `---
doctype: 📆
status: ${statusEmoji}
started: ${formatDate(daysAgo, 'iso')}
namespace: ${ns}
workstream: ${wsEmoji}
initiative:
---`
}

function meetingFrontmatter(ns, daysAgo) {
  return `---
doctype: 🗒️
started: ${formatDate(daysAgo, 'yymmdd')}
namespace: ${ns}
---`
}

// ─── HTML form ────────────────────────────────────────────────────────────────

function buildFormHTML(initialType, allWorkstreams) {
  const todayISO = formatDate(0, 'iso')
  const data = JSON.stringify({
    workstreams: allWorkstreams,
    statusOptions: STATUS_OPTIONS,
    devProjects: DEV_PROJECT_OPTIONS.filter(p => p !== '— none —'),
    domainEmojis: DOMAIN_EMOJIS,
    todayISO,
  })

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #ffffff; --surface: #f2f2f7; --border: #e0e0e5;
    --text: #000000; --text2: #6e6e73; --accent: #007AFF; --accent-dim: #cce0ff;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #1c1c1e; --surface: #2c2c2e; --border: #3a3a3c;
            --text: #ffffff; --text2: #8e8e93; --accent-dim: #0a3060; }
  }
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif;
         background: var(--bg); color: var(--text);
         padding: 18px 18px 14px; font-size: 14px; line-height: 1.4; }
  h2 { font-size: 16px; font-weight: 600; margin-bottom: 14px; }
  .field { margin-bottom: 12px; }
  label { display: block; font-size: 11px; font-weight: 600; color: var(--text2);
          text-transform: uppercase; letter-spacing: .5px; margin-bottom: 5px; }
  .pills { display: flex; gap: 5px; flex-wrap: wrap; }
  .pill { height: 30px; padding: 0 12px; border-radius: 99px;
          border: 1.5px solid var(--border); background: var(--surface);
          color: var(--text); font-size: 13px; font-weight: 500; cursor: pointer;
          transition: all .1s; display: flex; align-items: center; gap: 3px;
          white-space: nowrap; }
  .pill:hover { border-color: var(--accent); color: var(--accent); }
  .pill.active { background: var(--accent); border-color: var(--accent); color: #fff; }
  select, input[type=text], input[type=date] {
    width: 100%; height: 34px; padding: 0 10px;
    background: var(--surface); border: 1.5px solid var(--border);
    border-radius: 8px; color: var(--text); font-size: 14px;
    font-family: inherit; appearance: none; -webkit-appearance: none; outline: none; }
  .cal-trigger { height: 48px; padding: 0 14px; display: flex; align-items: center;
    background: var(--surface); border: 1.5px solid var(--border); border-radius: 10px;
    cursor: pointer; font-size: 17px; color: var(--text); user-select: none; }
  .cal-trigger:hover { border-color: var(--accent); color: var(--accent); }
  .cal-wrap { position: relative; }
  .cal { position: absolute; top: calc(48px + 6px); left: 0; right: 0;
    background: var(--bg); border: 1.5px solid var(--border); border-radius: 12px;
    padding: 12px; z-index: 20; box-shadow: 0 4px 24px rgba(0,0,0,.18); }
  .cal.hidden { display: none; }
  .cal-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
  .cal-hdr span { font-size: 15px; font-weight: 600; }
  .cal-hdr button { width: 30px; height: 30px; border-radius: 7px;
    border: 1.5px solid var(--border); background: var(--surface);
    cursor: pointer; font-size: 16px; color: var(--text); line-height: 1; }
  .cal-hdr button:hover { border-color: var(--accent); color: var(--accent); }
  .cal-dow { display: grid; grid-template-columns: repeat(7,1fr); gap: 2px; margin-bottom: 4px; }
  .cal-dow span { text-align: center; font-size: 11px; font-weight: 600; color: var(--text2); padding: 3px 0; }
  .cal-days { display: grid; grid-template-columns: repeat(7,1fr); gap: 2px; }
  .cd { height: 36px; border-radius: 7px; border: none; background: none;
    cursor: pointer; font-size: 13px; color: var(--text);
    display: flex; align-items: center; justify-content: center; }
  .cd:hover:not(.cd-future):not(.cd-empty) { background: var(--accent-dim); color: var(--accent); }
  .cd.cd-today { font-weight: 700; color: var(--accent); }
  .cd.cd-sel { background: var(--accent) !important; color: #fff !important; border-radius: 7px; }
  .cd.cd-future { color: var(--text2); opacity: .3; cursor: not-allowed; }
  .cd.cd-empty { cursor: default; }
  select { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%238e8e93' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
            background-repeat: no-repeat; background-position: right 10px center; padding-right: 28px; }
  input[type=text]:focus, select:focus, input[type=date]:focus { border-color: var(--accent); }
  .row { display: flex; gap: 10px; }
  .row .field { flex: 1; }
  /* Filename preview */
  .preview-wrap { margin-top: 6px; padding: 7px 10px; background: var(--accent-dim);
                  border-radius: 7px; font-size: 12px; word-break: break-all; line-height: 1.5; }
  .preview-prefix { color: var(--accent); font-weight: 500; }
  .preview-suffix { color: var(--text); }
  .preview-placeholder { color: var(--text2); }
  .actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 14px; }
  .btn { height: 34px; padding: 0 16px; border-radius: 8px; border: none;
         font-size: 14px; font-weight: 500; cursor: pointer; font-family: inherit; }
  .btn-cancel { background: var(--surface); color: var(--text); border: 1.5px solid var(--border); }
  .btn-create { background: var(--accent); color: #fff; min-width: 76px; }
  .btn-create:disabled { opacity: .4; cursor: not-allowed; }
  .hidden { display: none !important; }
  #err { font-size: 12px; color: #ff3b30; margin-top: 6px; min-height: 14px; }
</style>
</head>
<body>
<h2>New Note</h2>

<div class="field">
  <label>Type</label>
  <div class="pills" id="type-pills">
    <button class="pill" data-val="plan">📆 Plan</button>
    <button class="pill" data-val="meeting">🗒️ Meeting</button>
    <button class="pill" data-val="note">📝 Note</button>
  </div>
</div>

<div class="field">
  <label>Domain</label>
  <div class="pills" id="domain-pills">
    <button class="pill" data-val="work">🏢 Work</button>
    <button class="pill" data-val="personal">🏡 Personal</button>
    <button class="pill" data-val="coffee">☕️ Coffee</button>
    <button class="pill" data-val="earlbear">👥 EarlBear</button>
  </div>
</div>

<div class="field hidden" id="ws-field">
  <label id="ws-label">Workstream</label>
  <select id="ws-select"></select>
</div>

<div class="field hidden" id="proj-field">
  <label>Project</label>
  <select id="proj-select"></select>
</div>

<div class="row">
  <div class="field hidden" id="status-field">
    <label>Status</label>
    <select id="status-select"></select>
  </div>
  <div class="field hidden" id="date-field">
    <label>Meeting date</label>
    <input type="date" id="meeting-date" style="display:none">
    <div class="cal-wrap">
      <div class="cal-trigger" id="cal-trigger" onclick="toggleCal()">—</div>
      <div class="cal hidden" id="cal">
        <div class="cal-hdr">
          <button type="button" onclick="calNav(-1)">&#8249;</button>
          <span id="cal-lbl"></span>
          <button type="button" onclick="calNav(1)">&#8250;</button>
        </div>
        <div class="cal-dow"><span>Su</span><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span></div>
        <div class="cal-days" id="cal-days"></div>
      </div>
    </div>
  </div>
</div>

<div class="field">
  <label>Title</label>
  <input type="text" id="title" placeholder="Descriptive title…" autocomplete="off" spellcheck="false">
  <div class="preview-wrap" id="preview">
    <span class="preview-prefix" id="preview-prefix"></span><span class="preview-placeholder" id="preview-ph">your title here</span>
  </div>
</div>

<div id="err"></div>

<div class="actions">
  <button class="btn btn-cancel" onclick="cancel()">Cancel</button>
  <button class="btn btn-create" id="create-btn" onclick="submit()">Create</button>
</div>

<script>
const C = ${data};
let type = 'plan', domain = 'work';
const $ = id => document.getElementById(id);

function setOptions(sel, opts, defaultIdx) {
  sel.innerHTML = opts.map((o,i) =>
    '<option value="' + o + '"' + (i===defaultIdx?' selected':'') + '>' + o + '</option>'
  ).join('');
}

function activatePill(groupId, val) {
  document.querySelectorAll('#' + groupId + ' .pill').forEach(p =>
    p.classList.toggle('active', p.dataset.val === val));
}

// ── Prefix computation ──────────────────────────────────────────────────────

function dateFromISO(iso) {
  // Parse YYYY-MM-DD without timezone shift
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function toYYMMDD(d) {
  const yy = String(d.getFullYear()).slice(2);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return yy + mm + dd;
}

function computePrefix() {
  const de = C.domainEmojis[domain];
  if (type === 'note') return de + '📝 ';
  const wsVal = $('ws-select').value || '';
  const projVal = $('proj-select').value || '';
  const useProj = projVal && projVal !== '— no project —';
  const wsEmoji = (useProj ? projVal : wsVal).split(' ')[0];
  if (type === 'meeting') {
    const iso = ($('meeting-date') && $('meeting-date').value) ? $('meeting-date').value : C.todayISO;
    return de + ' ' + toYYMMDD(dateFromISO(iso)) + ' ';
  }
  return de + toYYMMDD(dateFromISO(C.todayISO)) + wsEmoji + ' ';
}

function updatePreview() {
  const prefix = computePrefix();
  const suffix = $('title').value;
  $('preview-prefix').textContent = prefix;
  const ph = $('preview-ph');
  if (suffix) { ph.className = 'preview-suffix'; ph.textContent = suffix; }
  else        { ph.className = 'preview-placeholder'; ph.textContent = 'your title here'; }
}

// ── Field visibility ────────────────────────────────────────────────────────

function updateWsField() {
  const ws = C.workstreams[domain] || [];
  if (type === 'note' || ws.length === 0) {
    $('ws-field').classList.add('hidden');
    $('proj-field').classList.add('hidden');
    return;
  }
  $('ws-label').textContent = domain === 'personal' ? 'Activity' : 'Workstream';
  setOptions($('ws-select'), ws, 0);
  $('ws-field').classList.remove('hidden');
  updateProjField();
}

function updateProjField() {
  const wsVal = $('ws-select').value || '';
  const isDev = wsVal.includes('Development');
  const show = type === 'plan' && isDev && (domain === 'work' || domain === 'earlbear');
  if (show) {
    setOptions($('proj-select'), ['— no project —'].concat(C.devProjects), 0);
    $('proj-field').classList.remove('hidden');
  } else {
    $('proj-field').classList.add('hidden');
  }
}

function refresh() {
  $('status-field').classList.toggle('hidden', type !== 'plan');
  $('date-field').classList.toggle('hidden', type !== 'meeting');
  updateWsField();
  updatePreview();
}

// ── Event wiring ─────────────────────────────────────────────────────────────

function pillGroup(id, setter) {
  document.getElementById(id).addEventListener('click', e => {
    const p = e.target.closest('.pill');
    if (!p) return;
    setter(p.dataset.val);
    activatePill(id, p.dataset.val);
    refresh();
  });
}

pillGroup('type-pills', v => { type = v; });
pillGroup('domain-pills', v => { domain = v; });
$('ws-select').addEventListener('change', () => { updateProjField(); updatePreview(); });
$('proj-select').addEventListener('change', updatePreview);
$('title').addEventListener('input', updatePreview);

// ── Calendar picker ───────────────────────────────────────────────────────────

var CAL_MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
var CAL_MONTHS_S = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
var CAL_DAYS_S = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
var calY, calM;

function calISOToDate(iso) { var p=iso.split('-'); return new Date(+p[0],+p[1]-1,+p[2]); }
function calDateToISO(d) { return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
function calSameDay(a,b) { return a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate(); }

function calRender() {
  $('cal-lbl').textContent = CAL_MONTHS[calM] + ' ' + calY;
  var today = calISOToDate(C.todayISO);
  var sel = $('meeting-date').value ? calISOToDate($('meeting-date').value) : today;
  var first = new Date(calY, calM, 1);
  var last = new Date(calY, calM+1, 0);
  var html = '';
  for (var i=0; i<first.getDay(); i++) html += '<div class="cd cd-empty"></div>';
  for (var d=1; d<=last.getDate(); d++) {
    var dt = new Date(calY, calM, d);
    var iso = calDateToISO(dt);
    var cls = 'cd';
    if (dt > today) { cls += ' cd-future'; html += '<div class="'+cls+'">'+d+'</div>'; continue; }
    if (calSameDay(dt, today)) cls += ' cd-today';
    if (calSameDay(dt, sel)) cls += ' cd-sel';
    html += '<div class="'+cls+'" data-iso="'+iso+'" onclick="calPick(this.dataset.iso)">'+d+'</div>';
  }
  $('cal-days').innerHTML = html;
}

function calNav(dir) {
  calM += dir;
  if (calM<0){calM=11;calY--;} if (calM>11){calM=0;calY++;}
  calRender();
}

function calPick(iso) {
  $('meeting-date').value = iso;
  calUpdateTrigger();
  $('cal').classList.add('hidden');
  updatePreview();
}

function calUpdateTrigger() {
  var iso = $('meeting-date').value || C.todayISO;
  var d = calISOToDate(iso);
  $('cal-trigger').textContent = CAL_DAYS_S[d.getDay()]+', '+CAL_MONTHS_S[d.getMonth()]+' '+d.getDate()+', '+d.getFullYear();
}

function toggleCal() {
  var cal = $('cal');
  if (cal.classList.contains('hidden')) {
    var iso = $('meeting-date').value || C.todayISO;
    var d = calISOToDate(iso);
    calY = d.getFullYear(); calM = d.getMonth();
    calRender();
    cal.classList.remove('hidden');
  } else {
    cal.classList.add('hidden');
  }
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('.cal-wrap')) $('cal').classList.add('hidden');
});

// ── Init ─────────────────────────────────────────────────────────────────────

setOptions($('status-select'), C.statusOptions, 2);
$('meeting-date').value = C.todayISO;
calUpdateTrigger();

type = '${initialType}';
domain = 'work';
activatePill('type-pills', type);
activatePill('domain-pills', domain);
refresh();

var focusTimer = setTimeout(() => $('title').focus(), 60);

// Named handler so submit() and cancel() can remove it, letting native Esc close the window.
// (win.close() from plugin code quits the entire app — NotePlan bug — so we rely on native close.)
function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  if (e.key === 'Escape') cancel();
}
document.addEventListener('keydown', handleKeyDown);

// ── Submit ────────────────────────────────────────────────────────────────────

function submit() {
  const title = $('title').value.trim();
  if (!title) { $('title').focus(); return; }
  const wsVal = $('ws-select').value || '';
  const projVal = $('proj-select').value || '';
  const workstream = (projVal && projVal !== '— no project —') ? projVal : wsVal;
  let daysAgo = 0;
  if (type === 'meeting') {
    const sel = $('meeting-date').value || C.todayISO;
    daysAgo = Math.max(0, Math.round(
      (dateFromISO(C.todayISO) - dateFromISO(sel)) / 86400000
    ));
  }
  const params = { domain, type, title, workstream,
    status: $('status-select').value || C.statusOptions[2], daysAgo };
  $('create-btn').disabled = true;

  var paramsJSON = JSON.stringify(params);
  var safeParams2 = JSON.stringify(paramsJSON);
  var code = '(function(){ DataStore.invokePluginCommandByName("Create Note (API)","oeid.noteplan-quicknote",[' + safeParams2 + ']); })()';
  window.webkit.messageHandlers.jsBridge.postMessage({ code: code, onHandle: '', id: 'create' });

  document.removeEventListener('keydown', handleKeyDown);
  clearTimeout(focusTimer);
  document.body.innerHTML = '<div style="font-family:-apple-system,sans-serif;padding:40px 24px;text-align:center">' +
    '<div style="font-size:32px;margin-bottom:12px">✓</div>' +
    '<div style="font-size:15px;font-weight:600;color:#007AFF">Note created</div>' +
    '</div>';
}

function cancel() {
  $('cal').classList.add('hidden');
  document.removeEventListener('keydown', handleKeyDown);
  clearTimeout(focusTimer);
  var code = '(function(){ DataStore.invokePluginCommandByName("Close Quick Note","oeid.noteplan-quicknote",[]); })()';
  window.webkit.messageHandlers.jsBridge.postMessage({ code: code, onHandle: '', id: 'cancel' });
}
</script>
</body>
</html>`
}

async function showCreateForm(initialType = 'plan') {
  const allWorkstreams = {
    work:     getWorkstreams('work'),
    personal: getWorkstreams('personal'),
    coffee:   getWorkstreams('coffee'),
    earlbear: getWorkstreams('earlbear'),
  }
  const html = buildFormHTML(initialType, allWorkstreams)
  await HTMLView.showWindowWithOptions(html, 'New Note', {
    width: 460, height: 520, shouldFocus: true, customId: 'oeid-quicknote-form',
  })
}

// ─── closeQuickNote / createAndClose ─────────────────────────────────────────

async function closeQuickNote() {
  for (const win of NotePlan.htmlWindows) {
    if (win.customId === 'oeid-quicknote-form') {
      win.close()
      return
    }
  }
}


// ─── /plan ────────────────────────────────────────────────────────────────────

async function plan() { await showCreateForm('plan') }

// ─── /meeting ─────────────────────────────────────────────────────────────────

async function meeting() { await showCreateForm('meeting') }

// ─── /note ────────────────────────────────────────────────────────────────────

async function note() { await showCreateForm('note') }

// ─── createNote (programmatic entry point for other plugins) ─────────────────
//
// Called via: DataStore.invokePluginCommandByName('oeid.noteplan-quicknote', 'createNote', [jsonParams])
//
// params JSON shape:
//   { domain, type, title, workstream?, status?, daysAgo? }
//   domain:    'work' | 'personal' | 'coffee' | 'earlbear'
//   type:      'plan' | 'meeting' | 'note'
//   title:     string
//   workstream: emoji+name string, e.g. '🧑🏻‍💻 Development' (plans only)
//   status:    emoji+label string, e.g. '🟢 Started' (plans only, default '🚦 Ready')
//   daysAgo:   number (meetings only, default 0)
//
async function createNote(jsonParams) {
  let params
  try {
    params = typeof jsonParams === 'string' ? JSON.parse(jsonParams) : jsonParams
  } catch (e) {
    await CommandBar.prompt('createNote error', `Invalid params: ${jsonParams}`, ['OK'])
    return
  }

  const { domain, type, title, workstream = '', status = '🚦 Ready', daysAgo = 0 } = params
  if (!domain || !type || !title) return

  const wsEmoji = workstream ? workstream.split(' ')[0] : ''
  const statusEmoji = status.split(' ')[0]
  const date = formatDate(daysAgo, 'yymmdd')
  const domainEmoji = DOMAIN_EMOJIS[domain]

  let filename, folder, content

  if (type === 'plan') {
    filename = `${domainEmoji}${date}${wsEmoji} ${title}`
    folder = WORKSTREAM_IS_FOLDER[domain] && workstream
      ? PLAN_ROOTS[domain] + '/' + workstream
      : PLAN_ROOTS[domain]
    if (domain === 'work') content = planBody(filename, workPlanFrontmatter(wsEmoji, statusEmoji, daysAgo), daysAgo)
    else if (domain === 'personal') content = planBody(filename, personalPlanFrontmatter(wsEmoji, statusEmoji, daysAgo), daysAgo)
    else content = planBody(filename, domainPlanFrontmatter(NAMESPACE[domain], wsEmoji, statusEmoji, daysAgo), daysAgo)
  } else if (type === 'meeting') {
    filename = `${domainEmoji} ${date} ${title}`
    folder = MEETING_FOLDERS[domain]
    const fm = meetingFrontmatter(NAMESPACE[domain], daysAgo)
    content = meetingBody(filename, fm, daysAgo, domain === 'work')
  } else if (type === 'note') {
    filename = `${domainEmoji}📝 ${title}`
    folder = NOTE_FOLDERS[domain]
    content = noteBody(filename, NAMESPACE[domain])
  }

  if (!filename || !folder || !content) return
  await closeQuickNote()
  await createAndOpen(filename, folder, content)
}

// Allow pure-function testing in Node.js (module is undefined in NotePlan's JS context)
if (typeof module !== 'undefined') {
  module.exports = {
    domainKey,
    formatDate,
    getWorkstreams,
    planBody,
    meetingBody,
    noteBody,
    workPlanFrontmatter,
    personalPlanFrontmatter,
    domainPlanFrontmatter,
    meetingFrontmatter,
    PLAN_ROOTS,
    MEETING_FOLDERS,
    NOTE_FOLDERS,
    DOMAIN_EMOJIS,
    NAMESPACE,
    createNote,
    buildFormHTML,
  }
}
