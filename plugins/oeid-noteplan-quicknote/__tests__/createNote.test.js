const createdNotes = []

global.DataStore = {
  folders: [
    '🏢 ServiceNow/📆 Plans/🧑🏻‍💻 Development',
    '🏢 ServiceNow/📆 Plans/🎯 Impact',
    '🏡 Personal/🏡📆 Plans/Present/👨🏻‍💻 Development',
  ],
  newNote(title, folder) {
    createdNotes.push({ title, folder })
    return `${folder}/${title}.md`
  },
}
global.Editor = {
  openNoteByFilename: jest.fn().mockResolvedValue(true),
  content: '',
}
global.CommandBar = {
  prompt: jest.fn().mockResolvedValue(0),
}

const { createNote } = require('../script.js')

const RealDate = Date
beforeEach(() => {
  createdNotes.length = 0
  jest.clearAllMocks()
  global.Date = class extends RealDate {
    constructor(...args) { return args.length ? new RealDate(...args) : new RealDate('2026-04-22T12:00:00Z') }
    static now() { return new RealDate('2026-04-22T12:00:00Z').getTime() }
  }
})
afterEach(() => { global.Date = RealDate })

describe('createNote — plan', () => {
  test('work plan: correct filename and folder', async () => {
    await createNote({ domain: 'work', type: 'plan', title: 'Build Plugin', workstream: '🧑🏻‍💻 Development', status: '🟢 Started' })
    expect(createdNotes[0].title).toBe('🏢260422🧑🏻‍💻 Build Plugin')
    expect(createdNotes[0].folder).toBe('🏢 ServiceNow/📆 Plans/🧑🏻‍💻 Development')
  })

  test('personal plan: correct filename and folder', async () => {
    await createNote({ domain: 'personal', type: 'plan', title: 'Elgato Setup', workstream: '👨🏻‍💻 Development', status: '🚦 Ready' })
    expect(createdNotes[0].title).toBe('🏡260422👨🏻‍💻 Elgato Setup')
    expect(createdNotes[0].folder).toContain('🏡 Personal')
  })

  test('NaqshCoffee plan', async () => {
    await createNote({ domain: 'coffee', type: 'plan', title: 'Design System', workstream: '🎨 Design', status: '🟢 Started' })
    expect(createdNotes[0].title).toBe('☕️260422🎨 Design System')
  })

  test('EarlBear plan', async () => {
    await createNote({ domain: 'earlbear', type: 'plan', title: 'Infrastructure', workstream: '🧑🏻‍💻 Development', status: '🟢 Started' })
    expect(createdNotes[0].title).toBe('👥260422🧑🏻‍💻 Infrastructure')
  })

  test('default status when omitted', async () => {
    await createNote({ domain: 'work', type: 'plan', title: 'Quick Plan', workstream: '🎯 Impact' })
    expect(createdNotes[0].title).toBe('🏢260422🎯 Quick Plan')
  })
})

describe('createNote — meeting', () => {
  test('work meeting: space after domain emoji', async () => {
    await createNote({ domain: 'work', type: 'meeting', title: '1-1 Ritesh', daysAgo: 0 })
    expect(createdNotes[0].title).toBe('🏢 260422 1-1 Ritesh')
    expect(createdNotes[0].folder).toBe('🏢 ServiceNow/👤 Meetings')
  })

  test('personal meeting backdated 1 day', async () => {
    await createNote({ domain: 'personal', type: 'meeting', title: 'Family Sync', daysAgo: 1 })
    expect(createdNotes[0].title).toBe('🏡 260421 Family Sync')
  })

  test('EarlBear meeting uses 👥 Meetings folder', async () => {
    await createNote({ domain: 'earlbear', type: 'meeting', title: 'Saad Sync', daysAgo: 0 })
    expect(createdNotes[0].folder).toBe('👥 EarlBear/👥 Meetings')
  })
})

describe('createNote — note', () => {
  test('work note', async () => {
    await createNote({ domain: 'work', type: 'note', title: 'ServiceNow Quirks' })
    expect(createdNotes[0].title).toBe('🏢📝 ServiceNow Quirks')
    expect(createdNotes[0].folder).toBe('🏢 ServiceNow/📝 Notes')
  })
})

describe('createNote — JSON string params', () => {
  test('accepts stringified JSON', async () => {
    await createNote(JSON.stringify({ domain: 'work', type: 'plan', title: 'Test', workstream: '🎯 Impact', status: '🚦 Ready' }))
    expect(createdNotes[0].title).toBe('🏢260422🎯 Test')
  })
})

describe('createNote — guard clauses', () => {
  test('does nothing when title missing', async () => {
    await createNote({ domain: 'work', type: 'plan', workstream: '🎯 Impact' })
    expect(createdNotes).toHaveLength(0)
  })

  test('shows error for invalid JSON', async () => {
    await createNote('not-json')
    expect(CommandBar.prompt).toHaveBeenCalled()
    expect(createdNotes).toHaveLength(0)
  })
})
