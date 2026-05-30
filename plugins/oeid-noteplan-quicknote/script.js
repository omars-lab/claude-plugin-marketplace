/* global DataStore, Editor, CommandBar */
// oeid.noteplan-quicknote — /plan /meeting /note
// Workstreams/activities are discovered at runtime from DataStore.folders.
// Adding a new workstream folder surfaces it automatically — no code change needed.

// ─── Static config ────────────────────────────────────────────────────────────

const DOMAIN_LABELS = ['Work', 'Personal', 'NaqshCoffee', 'EarlBear']
const NOTE_DOMAIN_LABELS = ['Work', 'Personal', 'NaqshCoffee']

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

async function getText(placeholder) {
  const result = await CommandBar.textPrompt('', placeholder, '')
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

// ─── /plan ────────────────────────────────────────────────────────────────────

async function plan() {
  const domainLabel = await pick(DOMAIN_LABELS, 'Domain')
  if (!domainLabel) return
  const domain = domainKey(domainLabel)

  const workstreams = getWorkstreams(domain)
  const wsPH = domain === 'personal' ? 'Activity' : 'Workstream'
  const wsLabel = workstreams.length ? await pick(workstreams, wsPH) : null
  if (workstreams.length && !wsLabel) return

  const wsEmoji = wsLabel ? wsLabel.split(' ')[0] : ''

  // Folder: only work/personal use workstream as a subfolder; coffee/earlbear do not
  let filenameEmoji = wsEmoji
  let folder = WORKSTREAM_IS_FOLDER[domain] && wsLabel
    ? PLAN_ROOTS[domain] + '/' + wsLabel
    : PLAN_ROOTS[domain]
  if (wsEmoji === '🧑🏻‍💻') {
    const proj = await pick(DEV_PROJECT_OPTIONS, 'Project (optional)')
    if (proj && proj !== '— none —') {
      filenameEmoji = proj.split(' ')[0]
      folder = folder + '/' + proj
    }
  }

  const title = await getText('Plan title')
  if (!title) return

  const statusLabel = await pick(STATUS_OPTIONS, 'Status')
  if (!statusLabel) return
  const statusEmoji = statusLabel.split(' ')[0]

  const date = formatDate(0, 'yymmdd')
  const domainEmoji = DOMAIN_EMOJIS[domain]
  const filename = `${domainEmoji}${date}${filenameEmoji} ${title}`

  let fm, content
  if (domain === 'work') {
    fm = workPlanFrontmatter(filenameEmoji, statusEmoji, 0)
  } else if (domain === 'personal') {
    fm = personalPlanFrontmatter(filenameEmoji, statusEmoji, 0)
  } else {
    fm = domainPlanFrontmatter(NAMESPACE[domain], filenameEmoji, statusEmoji, 0)
  }
  content = planBody(filename, fm, 0)

  await createAndOpen(filename, folder, content)
}

// ─── /meeting ─────────────────────────────────────────────────────────────────

async function meeting() {
  const domainLabel = await pick(DOMAIN_LABELS, 'Domain')
  if (!domainLabel) return
  const domain = domainKey(domainLabel)

  const title = await getText('Meeting title')
  if (!title) return

  const daysAgoStr = await pick(DAYS_AGO_OPTIONS, 'Days ago')
  if (daysAgoStr === null) return
  const daysAgo = Number(daysAgoStr)

  const date = formatDate(daysAgo, 'yymmdd')
  const domainEmoji = DOMAIN_EMOJIS[domain]
  const filename = `${domainEmoji} ${date} ${title}`
  const folder = MEETING_FOLDERS[domain]
  const fm = meetingFrontmatter(NAMESPACE[domain], daysAgo)
  const content = meetingBody(filename, fm, daysAgo, domain === 'work')

  await createAndOpen(filename, folder, content)
}

// ─── /note ────────────────────────────────────────────────────────────────────

async function note() {
  const domainLabel = await pick(NOTE_DOMAIN_LABELS, 'Domain')
  if (!domainLabel) return
  const domain = domainKey(domainLabel)

  const title = await getText('Note title')
  if (!title) return

  const domainEmoji = DOMAIN_EMOJIS[domain]
  const filename = `${domainEmoji}📝 ${title}`
  const folder = NOTE_FOLDERS[domain]

  await createAndOpen(filename, folder, noteBody(filename, NAMESPACE[domain]))
}

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
