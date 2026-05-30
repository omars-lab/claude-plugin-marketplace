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
  const data = JSON.stringify({
    workstreams: allWorkstreams,
    statusOptions: STATUS_OPTIONS,
    daysAgoOptions: DAYS_AGO_OPTIONS,
    devProjects: DEV_PROJECT_OPTIONS.filter(p => p !== '— none —'),
    meetingTitlePrefill: MEETING_TITLE_PREFILL,
    planTitlePrefill: PLAN_TITLE_PREFILL,
    domainEmojis: DOMAIN_EMOJIS,
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
    --text: #000000; --text2: #6e6e73; --accent: #007AFF;
    --radius: 10px;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #1c1c1e; --surface: #2c2c2e; --border: #3a3a3c;
            --text: #ffffff; --text2: #8e8e93; }
  }
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif;
         background: var(--bg); color: var(--text);
         padding: 20px 20px 16px; font-size: 14px; line-height: 1.4; }
  h2 { font-size: 17px; font-weight: 600; margin-bottom: 16px; }
  .field { margin-bottom: 14px; }
  label { display: block; font-size: 11px; font-weight: 600;
          color: var(--text2); text-transform: uppercase; letter-spacing: .5px;
          margin-bottom: 6px; }
  .pills { display: flex; gap: 6px; flex-wrap: wrap; }
  .pill { height: 32px; padding: 0 13px; border-radius: 99px;
          border: 1.5px solid var(--border); background: var(--surface);
          color: var(--text); font-size: 13px; font-weight: 500; cursor: pointer;
          transition: all .12s; display: flex; align-items: center; gap: 4px;
          white-space: nowrap; }
  .pill:hover { border-color: var(--accent); color: var(--accent); }
  .pill.active { background: var(--accent); border-color: var(--accent); color: #fff; }
  select, input[type=text] {
    width: 100%; height: 36px; padding: 0 10px;
    background: var(--surface); border: 1.5px solid var(--border);
    border-radius: 8px; color: var(--text); font-size: 14px;
    font-family: inherit; appearance: none; -webkit-appearance: none; outline: none; }
  select { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%238e8e93' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
            background-repeat: no-repeat; background-position: right 10px center;
            padding-right: 28px; }
  input[type=text]:focus, select:focus { border-color: var(--accent); }
  .row { display: flex; gap: 10px; }
  .row .field { flex: 1; }
  .actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 18px; }
  .btn { height: 36px; padding: 0 18px; border-radius: 8px; border: none;
         font-size: 14px; font-weight: 500; cursor: pointer; font-family: inherit; }
  .btn-cancel { background: var(--surface); color: var(--text); border: 1.5px solid var(--border); }
  .btn-create { background: var(--accent); color: #fff; min-width: 80px; }
  .btn-create:disabled { opacity: .4; cursor: not-allowed; }
  .hidden { display: none !important; }
  #err { font-size: 12px; color: #ff3b30; margin-top: 8px; min-height: 16px; }
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

<div class="field">
  <label>Title</label>
  <input type="text" id="title" placeholder="Note title" autocomplete="off" spellcheck="false">
</div>

<div class="row">
  <div class="field hidden" id="status-field">
    <label>Status</label>
    <select id="status-select"></select>
  </div>
  <div class="field hidden" id="days-field">
    <label>Days ago</label>
    <select id="days-select"></select>
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
    '<option value="' + o + '"' + (i === defaultIdx ? ' selected' : '') + '>' + o + '</option>'
  ).join('');
}

function activatePill(groupId, val) {
  document.querySelectorAll('#' + groupId + ' .pill').forEach(p => {
    p.classList.toggle('active', p.dataset.val === val);
  });
}

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
  const wsEmoji = ($('ws-select').value || '').split(' ')[0];
  const show = type === 'plan' && wsEmoji === '\\u{1F9D1}\\u200D\\u{1F4BB}' && (domain === 'work' || domain === 'earlbear');
  if (show) {
    setOptions($('proj-select'), ['— no project —'].concat(C.devProjects), 0);
    $('proj-field').classList.remove('hidden');
  } else {
    $('proj-field').classList.add('hidden');
  }
}

function updateTitlePrefill() {
  const t = $('title');
  if (t.value) return;
  const wsEmoji = ($('ws-select').value || '').split(' ')[0];
  const pre = type === 'meeting'
    ? (C.meetingTitlePrefill[domain] || '')
    : (C.planTitlePrefill[wsEmoji] || '');
  t.value = pre;
  t.setSelectionRange(pre.length, pre.length);
}

function refresh() {
  $('status-field').classList.toggle('hidden', type !== 'plan');
  $('days-field').classList.toggle('hidden', type !== 'meeting');
  updateWsField();
  updateTitlePrefill();
}

function pillGroup(id, setter) {
  document.getElementById(id).addEventListener('click', e => {
    const p = e.target.closest('.pill');
    if (!p) return;
    setter(p.dataset.val);
    activatePill(id, p.dataset.val);
    refresh();
  });
}

function submit() {
  const title = $('title').value.trim();
  if (!title) { $('title').focus(); return; }
  const wsVal = $('ws-select').value || '';
  const projVal = $('proj-select').value || '';
  const workstream = (projVal && projVal !== '\\u2014 no project \\u2014') ? projVal : wsVal;
  const params = {
    domain, type, title,
    workstream,
    status: $('status-select').value || C.statusOptions[2],
    daysAgo: Number($('days-select').value || 0),
  };
  $('create-btn').disabled = true;
  $('err').textContent = '';
  const code = JSON.stringify(
    '(async function(){try{await createNote(' + JSON.stringify(params) + ');return "ok";}catch(e){return "err:"+e.message;}})()'
  );
  window.webkit.messageHandlers.jsBridge.postMessage({ code, onHandle: 'onCreated', id: '1' });
}

function onCreated(result) {
  if (result === 'ok') { window.close(); }
  else { $('err').textContent = result || 'Unknown error'; $('create-btn').disabled = false; }
}

function cancel() { window.close(); }

// Init
pillGroup('type-pills', v => { type = v; });
pillGroup('domain-pills', v => { domain = v; });
$('ws-select').addEventListener('change', () => { updateProjField(); updateTitlePrefill(); });
setOptions($('status-select'), C.statusOptions, 2);
setOptions($('days-select'), C.daysAgoOptions, 0);

// Set initial type + domain
type = '${initialType}';
domain = 'work';
activatePill('type-pills', type);
activatePill('domain-pills', domain);
refresh();

setTimeout(() => { $('title').focus(); }, 60);

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  if (e.key === 'Escape') cancel();
});
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
    width: 460, height: 480, shouldFocus: true, customId: 'oeid-quicknote-form',
  })
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
  }
}
