#!/usr/bin/env node
/**
 * CLI end-to-end tests for oeid-noteplan-quicknote.
 *
 * Provides lightweight real implementations of DataStore, Editor, CommandBar
 * backed by the actual NotePlan filesystem. No app required.
 *
 * Usage:
 *   node scripts/e2e.js
 *   node scripts/e2e.js --keep   # don't delete created files (for manual inspection)
 */

const fs = require('fs')
const path = require('path')
const os = require('os')

const KEEP = process.argv.includes('--keep')
const NOTES_ROOT = path.join(
  os.homedir(),
  'Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes'
)

// ─── NotePlan global stubs (real filesystem) ─────────────────────────────────

let _lastFilename = null
let _pendingContent = null

global.DataStore = {
  get folders() {
    const result = []
    function walk(dir, rel) {
      let entries
      try { entries = fs.readdirSync(dir, { withFileTypes: true }) } catch { return }
      for (const e of entries) {
        if (!e.isDirectory() || e.name.startsWith('@') || e.name.startsWith('.')) continue
        const child = rel ? `${rel}/${e.name}` : e.name
        result.push(child)
        walk(path.join(dir, e.name), child)
      }
    }
    walk(NOTES_ROOT, '')
    return result
  },
  newNote(title, folder) {
    const dir = path.join(NOTES_ROOT, folder)
    fs.mkdirSync(dir, { recursive: true })
    const filepath = path.join(dir, `${title}.md`)
    fs.writeFileSync(filepath, '')            // placeholder; content set via Editor.content
    _lastFilename = path.join(folder, `${title}.md`)
    return _lastFilename
  },
}

global.Editor = {
  async openNoteByFilename(filename) { _lastFilename = filename },
  set content(text) {
    if (!_lastFilename) return
    const p = path.join(NOTES_ROOT, _lastFilename)
    if (fs.existsSync(p)) fs.writeFileSync(p, text)
  },
}

global.CommandBar = {
  prompt: async () => 0,
  showOptions: async () => null,
  textPrompt: async () => null,
}

// ─── Load plugin ─────────────────────────────────────────────────────────────

const { createNote } = require('../script.js')

// ─── Test runner ─────────────────────────────────────────────────────────────

const GREEN  = '\x1b[32m'
const RED    = '\x1b[31m'
const YELLOW = '\x1b[33m'
const BLUE   = '\x1b[34m'
const NC     = '\x1b[0m'

let passed = 0, failed = 0
const created = []

async function test(label, params, expectedRelPath, contentChecks = []) {
  _lastFilename = null
  const fullPath = path.join(NOTES_ROOT, expectedRelPath)

  // Clean up any leftover
  if (fs.existsSync(fullPath)) fs.unlinkSync(fullPath)

  await createNote(params)

  const exists = fs.existsSync(fullPath)
  if (!exists) {
    console.log(`  ${RED}✗${NC} ${label}`)
    console.log(`    expected: ${expectedRelPath}`)
    failed++
    return
  }

  const content = fs.readFileSync(fullPath, 'utf8')
  const mismatches = contentChecks.filter(({ re }) => !re.test(content))
  if (mismatches.length) {
    console.log(`  ${RED}✗${NC} ${label} (file exists but content wrong)`)
    mismatches.forEach(m => console.log(`    missing: ${m.label}`))
    failed++
  } else {
    console.log(`  ${GREEN}✓${NC} ${label}`)
    passed++
  }

  created.push(fullPath)
  if (!KEEP) fs.unlinkSync(fullPath)
}

// ─── Test cases ──────────────────────────────────────────────────────────────

async function main() {
  const { formatDate } = require('../script.js')
  const ymd  = formatDate(0, 'yymmdd')
  const ymd1 = formatDate(1, 'yymmdd')

  console.log(`${BLUE}oeid-noteplan-quicknote — CLI e2e tests${NC}`)
  console.log(`${YELLOW}Notes root: ${NOTES_ROOT}${NC}\n`)

  // ── Plans ─────────────────────────────────────────────────────────────────

  console.log('Plans:')
  await test(
    'work plan — filename, folder, frontmatter',
    { domain: 'work', type: 'plan', title: 'e2e Test Plan', workstream: '🎯 Impact', status: '🟢 Started' },
    `🏢 ServiceNow/📆 Plans/🎯 Impact/🏢${ymd}🎯 e2e Test Plan.md`,
    [
      { label: 'H1 title',      re: /^# 🏢\d{6}🎯 e2e Test Plan$/m },
      { label: 'doctype: 📆',   re: /doctype: 📆/ },
      { label: 'namespace: 🏢', re: /namespace: 🏢/ },
      { label: 'workstream: 🎯',re: /workstream: 🎯/ },
      { label: 'status: 🟢',    re: /status: 🟢/ },
      { label: 'weekly checkbox',re: /Is \[\[.*\]\] done\? >\d{4}-W\d{2}/ },
    ]
  )

  await test(
    'personal plan — plantype key (not workstream)',
    { domain: 'personal', type: 'plan', title: 'e2e Test Plan', workstream: '🌱 Growth', status: '🔮 Future' },
    `🏡 Personal/🏡📆 Plans/Present/🌱 Growth/🏡${ymd}🌱 e2e Test Plan.md`,
    [
      { label: 'namespace: 🏡', re: /namespace: 🏡/ },
      { label: 'plantype: 🌱',  re: /plantype: 🌱/ },
      { label: 'no workstream key', re: /^(?!.*workstream:)/s },
    ]
  )

  await test(
    'NaqshCoffee plan',
    { domain: 'coffee', type: 'plan', title: 'e2e Test Plan', workstream: '🎨 Design', status: '🚦 Ready' },
    `☕️ NaqshCoffee/📆 Plans/☕️${ymd}🎨 e2e Test Plan.md`,
    [
      { label: 'namespace: ☕️', re: /namespace: ☕️/ },
      { label: 'workstream: 🎨', re: /workstream: 🎨/ },
    ]
  )

  await test(
    'EarlBear plan',
    { domain: 'earlbear', type: 'plan', title: 'e2e Test Plan', workstream: '👨🏻‍💼 Strategy', status: '🚦 Ready' },
    `👥 EarlBear/📆 Plans/👥${ymd}👨🏻‍💼 e2e Test Plan.md`,
    [
      { label: 'namespace: 👥', re: /namespace: 👥/ },
    ]
  )

  // ── Meetings ──────────────────────────────────────────────────────────────

  console.log('\nMeetings:')
  await test(
    'work meeting — space after emoji, Attendees/Agenda sections',
    { domain: 'work', type: 'meeting', title: 'e2e Test Meeting', daysAgo: 0 },
    `🏢 ServiceNow/👤 Meetings/🏢 ${ymd} e2e Test Meeting.md`,
    [
      { label: 'doctype: 🗒️',    re: /doctype: 🗒️/ },
      { label: 'namespace: 🏢',  re: /namespace: 🏢/ },
      { label: '## Attendees',   re: /## Attendees/ },
      { label: '## Agenda',      re: /## Agenda/ },
      { label: '## Action Items',re: /## Action Items/ },
    ]
  )

  await test(
    'work meeting backdated 1 day',
    { domain: 'work', type: 'meeting', title: 'e2e Backdated Meeting', daysAgo: 1 },
    `🏢 ServiceNow/👤 Meetings/🏢 ${ymd1} e2e Backdated Meeting.md`,
  )

  await test(
    'personal meeting — Notes + Action Items (no Agenda)',
    { domain: 'personal', type: 'meeting', title: 'e2e Test Meeting', daysAgo: 0 },
    `🏡 Personal/🏡👥 Meetings/🏡 ${ymd} e2e Test Meeting.md`,
    [
      { label: '## Notes',       re: /## Notes/ },
      { label: 'no ## Agenda',   re: /^(?!.*## Agenda)/s },
    ]
  )

  await test(
    'EarlBear meeting — 👥 Meetings (not 👥👤)',
    { domain: 'earlbear', type: 'meeting', title: 'e2e Test Meeting', daysAgo: 0 },
    `👥 EarlBear/👥 Meetings/👥 ${ymd} e2e Test Meeting.md`,
  )

  await test(
    'NaqshCoffee meeting',
    { domain: 'coffee', type: 'meeting', title: 'e2e Test Meeting', daysAgo: 0 },
    `☕️ NaqshCoffee/☕️👤 Meetings/☕️ ${ymd} e2e Test Meeting.md`,
  )

  // ── Notes ─────────────────────────────────────────────────────────────────

  console.log('\nNotes:')
  await test(
    'work note',
    { domain: 'work', type: 'note', title: 'e2e Test Note' },
    `🏢 ServiceNow/📝 Notes/🏢📝 e2e Test Note.md`,
    [
      { label: 'doctype: 📝', re: /doctype: 📝/ },
    ]
  )

  await test(
    'personal note',
    { domain: 'personal', type: 'note', title: 'e2e Test Note' },
    `🏡 Personal/🏡📝 Notes/🏡📝 e2e Test Note.md`,
  )

  await test(
    'EarlBear note',
    { domain: 'earlbear', type: 'note', title: 'e2e Test Note' },
    `👥 EarlBear/📝 Notes/👥📝 e2e Test Note.md`,
    [{ label: 'namespace: 👥', re: /namespace: 👥/ }]
  )

  // ── Guard clauses ─────────────────────────────────────────────────────────

  console.log('\nGuard clauses:')
  const countBefore = fs.readdirSync(path.join(NOTES_ROOT, '🏢 ServiceNow/📝 Notes')).length
  await createNote({ domain: 'work', type: 'note' })   // missing title
  const countAfter = fs.readdirSync(path.join(NOTES_ROOT, '🏢 ServiceNow/📝 Notes')).length
  if (countBefore === countAfter) {
    console.log(`  ${GREEN}✓${NC} missing title — no file created`)
    passed++
  } else {
    console.log(`  ${RED}✗${NC} missing title — file was incorrectly created`)
    failed++
  }

  // ── Summary ───────────────────────────────────────────────────────────────

  const total = passed + failed
  console.log(`\n${failed === 0 ? GREEN : RED}${passed}/${total} passed${NC}${KEEP ? `  ${YELLOW}(files kept for inspection)${NC}` : ''}`)
  process.exit(failed > 0 ? 1 : 0)
}

main().catch(e => { console.error(e); process.exit(1) })
