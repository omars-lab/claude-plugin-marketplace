/**
 * Form submit() tests — jsdom simulates the HTML window.
 *
 * submit() uses jsBridge with onHandle:'' (official NP pattern — no callback, no crash).
 * We capture postMessage calls and parse the code string to assert on params.
 */

const { JSDOM, VirtualConsole } = require('jsdom')
const silentConsole = new VirtualConsole()

global.DataStore = { folders: [] }
global.CommandBar = {}
global.Editor = {}
global.HTMLView = {}

const { buildFormHTML } = require('../script.js')

const WS = {
  work:     ['⚙️ AI Club', '🧑🏻‍💻 Development', '🎯 Impact'],
  personal: ['🌱 Growth', '📚 Learning'],
  coffee:   ['🎨 Design', '🏪 Site'],
  earlbear: ['🧑🏻‍💻 Development'],
}

function makeFormDOM(initialType = 'plan') {
  const html = buildFormHTML(initialType, WS)
  const mockScript = [
    '<script>',
    'window.__messages = [];',
    'window.webkit = { messageHandlers: { jsBridge: {',
    '  postMessage: function(m) { window.__messages.push(m); }',
    '} } };',
    '</script>',
  ].join('\n')
  const testHtml = html.replace(/(<script>\s*\nconst C =)/, mockScript + '\n$1')
  return new JSDOM(testHtml, { runScripts: 'dangerously', virtualConsole: silentConsole }).window
}

// Extract params from the create jsBridge message code string.
// Code: (async function(){ await DataStore.invokePluginCommandByName("...", "...", ["<json>"]); })()
function extractParams(win) {
  const createMsg = win.__messages.find(m => m.id === 'create')
  if (!createMsg) return null
  const match = createMsg.code.match(/\[("(?:[^"\\]|\\.)*")\]/)
  if (!match) return null
  return JSON.parse(JSON.parse(match[1]))
}

// ─── Tests ─────────────────────────────────────────────────────────────────────

describe('form submit()', () => {
  test('empty title does not call jsBridge', () => {
    const win = makeFormDOM('plan')
    win.submit()
    expect(win.__messages.length).toBe(0)
  })

  test('posts create message with onHandle empty string', () => {
    const win = makeFormDOM('plan')
    win.document.getElementById('title').value = 'Test'
    win.submit()
    const createMsg = win.__messages.find(m => m.id === 'create')
    expect(createMsg).toBeDefined()
    expect(createMsg.onHandle).toBe('')
    expect(createMsg.code).toMatch(/invokePluginCommandByName/)
  })

  test('work plan — correct domain, type, workstream, title', () => {
    const win = makeFormDOM('plan')
    win.document.getElementById('title').value = 'Build Feature'
    win.submit()
    const p = extractParams(win)
    expect(p).toMatchObject({
      domain: 'work', type: 'plan', title: 'Build Feature', workstream: '⚙️ AI Club',
    })
  })

  test('personal domain pill switches domain', () => {
    const win = makeFormDOM('plan')
    win.document.querySelector('#domain-pills .pill[data-val="personal"]').click()
    win.document.getElementById('title').value = 'Health Goal'
    win.submit()
    expect(extractParams(win)).toMatchObject({ domain: 'personal', type: 'plan' })
  })

  test('meeting type — daysAgo=0 for today', () => {
    const win = makeFormDOM('meeting')
    win.document.getElementById('title').value = '1-1 Ritesh'
    win.submit()
    expect(extractParams(win)).toMatchObject({ type: 'meeting', daysAgo: 0, title: '1-1 Ritesh' })
  })

  test('meeting type — past date produces correct daysAgo', () => {
    const win = makeFormDOM('meeting')
    const d = new Date()
    d.setDate(d.getDate() - 7)
    win.document.getElementById('meeting-date').value = d.toISOString().slice(0, 10)
    win.document.getElementById('title').value = 'Weekly Sync'
    win.submit()
    expect(extractParams(win).daysAgo).toBe(7)
  })

  test('note type — no workstream in params', () => {
    const win = makeFormDOM('note')
    win.document.getElementById('title').value = 'Random Thought'
    win.submit()
    const p = extractParams(win)
    expect(p).toMatchObject({ type: 'note', title: 'Random Thought' })
    expect(p.workstream).toBe('')
  })

  test('coffee domain', () => {
    const win = makeFormDOM('plan')
    win.document.querySelector('#domain-pills .pill[data-val="coffee"]').click()
    win.document.getElementById('title').value = 'Brand Colours'
    win.submit()
    expect(extractParams(win).domain).toBe('coffee')
  })

  test('earlbear domain', () => {
    const win = makeFormDOM('plan')
    win.document.querySelector('#domain-pills .pill[data-val="earlbear"]').click()
    win.document.getElementById('title').value = 'Strategy Review'
    win.submit()
    expect(extractParams(win).domain).toBe('earlbear')
  })
})

describe('computePrefix()', () => {
  test('work plan prefix', () => {
    expect(makeFormDOM('plan').computePrefix()).toMatch(/^🏢\d{6}⚙️ $/)
  })
  test('note prefix', () => {
    expect(makeFormDOM('note').computePrefix()).toBe('🏢📝 ')
  })
  test('meeting prefix', () => {
    expect(makeFormDOM('meeting').computePrefix()).toMatch(/^🏢 \d{6} $/)
  })
})
