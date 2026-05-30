#!/usr/bin/env node
/**
 * Live integration tests — requires NotePlan to be running.
 *
 * Each test follows the same cycle:
 *   1. Cleanup — remove any stale file from a previous run
 *   2. Create  — trigger createNote via x-callback-url (same path as the form)
 *   3. Poll    — wait up to TIMEOUT ms for the file to appear with content
 *   4. Validate — assert on filename location + frontmatter fields
 *   5. Cleanup — delete created file (unless --keep)
 *
 * Usage:
 *   node scripts/live-test.js          # runs all tests, cleans up
 *   node scripts/live-test.js --keep   # leaves created files for inspection
 */

const { execSync } = require('child_process')
const { existsSync, unlinkSync, readFileSync } = require('fs')
const path = require('path')

const NOTES_ROOT = path.join(
  process.env.HOME,
  'Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes'
)
const KEEP = process.argv.includes('--keep')
const POLL_INTERVAL = 500   // ms between filesystem checks
const TIMEOUT = 10_000      // max ms to wait for a note to appear with content

// ─── Helpers ──────────────────────────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)) }

function today() {
  const d = new Date()
  const yy = String(d.getFullYear()).slice(2)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return yy + mm + dd
}

function triggerCreateNote(params) {
  const arg0 = encodeURIComponent(JSON.stringify(params))
  const url = `noteplan://x-callback-url/runPlugin?pluginID=oeid.noteplan-quicknote&command=createNote&arg0=${arg0}`
  execSync(`open "${url}"`)
}

// Poll until the file exists AND its content matches all checks, or timeout.
async function waitForFile(fullPath, contentChecks) {
  const deadline = Date.now() + TIMEOUT
  while (Date.now() < deadline) {
    if (existsSync(fullPath)) {
      const body = readFileSync(fullPath, 'utf8')
      if (Object.values(contentChecks).every(v => body.includes(v))) return { ok: true }
      const missing = Object.entries(contentChecks).filter(([, v]) => !body.includes(v))
      if (Date.now() + POLL_INTERVAL >= deadline) return { ok: false, missing }
    }
    await sleep(POLL_INTERVAL)
  }
  return { ok: false, missing: [['file', '(never appeared)']] }
}

let pass = 0, fail = 0

async function test(desc, params, expectedFolder, expectedFile, contentChecks = {}) {
  const fullPath = path.join(NOTES_ROOT, expectedFolder, expectedFile + '.md')

  // 1. Cleanup stale file
  if (existsSync(fullPath)) unlinkSync(fullPath)

  // 2. Create via x-callback-url
  triggerCreateNote(params)

  // 3. Poll
  const result = await waitForFile(fullPath, contentChecks)

  // 4. Validate
  if (!result.ok) {
    console.log(`  \x1b[31m✗\x1b[0m ${desc}`)
    if (!existsSync(fullPath)) {
      console.log(`    file never created: ${expectedFolder}/${expectedFile}.md`)
    } else {
      result.missing.forEach(([k, v]) => console.log(`    missing "${v}" (${k})`))
    }
    fail++
    // 5. Cleanup even on failure (unless --keep)
    if (!KEEP && existsSync(fullPath)) unlinkSync(fullPath)
    return
  }

  console.log(`  \x1b[32m✓\x1b[0m ${desc}`)
  pass++
  // 5. Cleanup
  if (!KEEP) unlinkSync(fullPath)
}

// ─── Tests ────────────────────────────────────────────────────────────────────

async function main() {
  try {
    execSync('pgrep -x NotePlan', { stdio: 'pipe' })
  } catch {
    console.error('\x1b[31mNotePlan is not running — launch it first\x1b[0m')
    process.exit(1)
  }

  const D = today()
  console.log('\x1b[34moeid-noteplan-quicknote — live integration tests\x1b[0m')
  console.log(`\x1b[33mNotes root: ${NOTES_ROOT}\x1b[0m\n`)

  console.log('Plans:')
  await test(
    'work plan — correct folder + frontmatter',
    { domain: 'work', type: 'plan', title: 'Live Test Plan', workstream: '⚙️ AI Club', status: '🚦 Ready' },
    '🏢 ServiceNow/📆 Plans/⚙️ AI Club',
    `🏢${D}⚙️ Live Test Plan`,
    { doctype: 'doctype: 📆', namespace: 'namespace: 🏢', workstream: 'workstream: ⚙️' }
  )

  await test(
    'personal plan — plantype key in frontmatter',
    { domain: 'personal', type: 'plan', title: 'Live Test Plan', workstream: '🌱 Growth', status: '🚦 Ready' },
    '🏡 Personal/🏡📆 Plans/Present/🌱 Growth',
    `🏡${D}🌱 Live Test Plan`,
    { doctype: 'doctype: 📆', plantype: 'plantype: 🌱' }
  )

  await test(
    'NaqshCoffee plan — no subfolder',
    { domain: 'coffee', type: 'plan', title: 'Live Test Plan', workstream: '🎨 Design', status: '🚦 Ready' },
    '☕️ NaqshCoffee/📆 Plans',
    `☕️${D}🎨 Live Test Plan`,
    { namespace: 'namespace: ☕️' }
  )

  await test(
    'EarlBear plan — no subfolder',
    { domain: 'earlbear', type: 'plan', title: 'Live Test Plan', workstream: '🧑🏻‍💻 Development', status: '🚦 Ready' },
    '👥 EarlBear/📆 Plans',
    `👥${D}🧑🏻‍💻 Live Test Plan`,
    { namespace: 'namespace: 👥' }
  )

  console.log('\nMeetings:')
  await test(
    'work meeting — Attendees + Agenda sections',
    { domain: 'work', type: 'meeting', title: 'Live Test Meeting', daysAgo: 0 },
    '🏢 ServiceNow/👤 Meetings',
    `🏢 ${D} Live Test Meeting`,
    { attendees: '## Attendees', agenda: '## Agenda', actions: '## Action Items' }
  )

  await test(
    'personal meeting — Notes section, no Attendees',
    { domain: 'personal', type: 'meeting', title: 'Live Test Meeting', daysAgo: 0 },
    '🏡 Personal/🏡👥 Meetings',
    `🏡 ${D} Live Test Meeting`,
    { notes: '## Notes', actions: '## Action Items' }
  )

  await test(
    'EarlBear meeting — correct folder',
    { domain: 'earlbear', type: 'meeting', title: 'Live Test Meeting', daysAgo: 0 },
    '👥 EarlBear/👥 Meetings',
    `👥 ${D} Live Test Meeting`,
    { namespace: 'namespace: 👥' }
  )

  console.log('\nNotes:')
  await test(
    'work note',
    { domain: 'work', type: 'note', title: 'Live Test Note' },
    '🏢 ServiceNow/📝 Notes',
    '🏢📝 Live Test Note',
    { doctype: 'doctype: 📝', namespace: 'namespace: 🏢' }
  )

  await test(
    'personal note',
    { domain: 'personal', type: 'note', title: 'Live Test Note' },
    '🏡 Personal/🏡📝 Notes',
    '🏡📝 Live Test Note',
    { doctype: 'doctype: 📝', namespace: 'namespace: 🏡' }
  )

  const color = fail === 0 ? '\x1b[32m' : '\x1b[31m'
  console.log(`\n${color}${pass}/${pass + fail} passed\x1b[0m`)
  if (fail > 0) process.exit(1)
}

main()
