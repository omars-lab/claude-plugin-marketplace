global.DataStore = { folders: [] }
global.Editor = {}
global.CommandBar = {}

const { formatDate, DOMAIN_EMOJIS, PLAN_ROOTS, MEETING_FOLDERS, NOTE_FOLDERS } = require('../script.js')

// Filename construction mirrors the logic in plan(), meeting(), note()
function buildPlanFilename(domain, wsEmoji, title, daysAgo = 0) {
  const date = formatDate(daysAgo, 'yymmdd')
  return `${DOMAIN_EMOJIS[domain]}${date}${wsEmoji} ${title}`
}

function buildMeetingFilename(domain, title, daysAgo = 0) {
  const date = formatDate(daysAgo, 'yymmdd')
  return `${DOMAIN_EMOJIS[domain]} ${date} ${title}`
}

function buildNoteFilename(domain, title) {
  return `${DOMAIN_EMOJIS[domain]}📝 ${title}`
}

describe('Plan filename construction', () => {
  const RealDate = Date
  beforeEach(() => {
    global.Date = class extends RealDate {
      constructor(...args) { return args.length ? new RealDate(...args) : new RealDate('2026-04-22T12:00:00Z') }
      static now() { return new RealDate('2026-04-22T12:00:00Z').getTime() }
    }
  })
  afterEach(() => { global.Date = RealDate })

  test('work plan — no space between domain emoji and date', () => {
    expect(buildPlanFilename('work', '🧑🏻‍💻', 'Build Plugin'))
      .toBe('🏢260422🧑🏻‍💻 Build Plugin')
  })

  test('personal plan — no space between domain emoji and date', () => {
    expect(buildPlanFilename('personal', '👨🏻‍💻', 'Elgato Setup'))
      .toBe('🏡260422👨🏻‍💻 Elgato Setup')
  })

  test('NaqshCoffee plan', () => {
    expect(buildPlanFilename('coffee', '🎨', 'Design System'))
      .toBe('☕️260422🎨 Design System')
  })

  test('EarlBear plan', () => {
    expect(buildPlanFilename('earlbear', '🧑🏻‍💻', 'Infrastructure'))
      .toBe('👥260422🧑🏻‍💻 Infrastructure')
  })

  test('work plan backdated 7 days', () => {
    expect(buildPlanFilename('work', '🎯', 'Impact Review', 7))
      .toBe('🏢260415🎯 Impact Review')
  })
})

describe('Meeting filename construction', () => {
  const RealDate = Date
  beforeEach(() => {
    global.Date = class extends RealDate {
      constructor(...args) { return args.length ? new RealDate(...args) : new RealDate('2026-04-22T12:00:00Z') }
      static now() { return new RealDate('2026-04-22T12:00:00Z').getTime() }
    }
  })
  afterEach(() => { global.Date = RealDate })

  test('work meeting — space after domain emoji', () => {
    expect(buildMeetingFilename('work', '1-1 Ritesh'))
      .toBe('🏢 260422 1-1 Ritesh')
  })

  test('personal meeting', () => {
    expect(buildMeetingFilename('personal', 'Family Check-in'))
      .toBe('🏡 260422 Family Check-in')
  })

  test('NaqshCoffee meeting', () => {
    expect(buildMeetingFilename('coffee', 'Saad Call'))
      .toBe('☕️ 260422 Saad Call')
  })

  test('EarlBear meeting', () => {
    expect(buildMeetingFilename('earlbear', 'Saad Omar 1-1'))
      .toBe('👥 260422 Saad Omar 1-1')
  })

  test('backdated 1 day', () => {
    expect(buildMeetingFilename('work', 'Sprint Review', 1))
      .toBe('🏢 260421 Sprint Review')
  })
})

describe('Note filename construction', () => {
  test('work note', () => {
    expect(buildNoteFilename('work', 'ServiceNow Quirks')).toBe('🏢📝 ServiceNow Quirks')
  })

  test('personal note', () => {
    expect(buildNoteFilename('personal', 'Random Thought')).toBe('🏡📝 Random Thought')
  })

  test('NaqshCoffee note', () => {
    expect(buildNoteFilename('coffee', 'Brand Ideas')).toBe('☕️📝 Brand Ideas')
  })
})

describe('Folder routing', () => {
  test('work plans root', () => {
    expect(PLAN_ROOTS.work).toBe('🏢 ServiceNow/📆 Plans')
  })

  test('personal plans root', () => {
    expect(PLAN_ROOTS.personal).toBe('🏡 Personal/🏡📆 Plans/Present')
  })

  test('work meetings folder', () => {
    expect(MEETING_FOLDERS.work).toBe('🏢 ServiceNow/👤 Meetings')
  })

  test('EarlBear meetings folder uses 👥 Meetings (not 👥👤)', () => {
    expect(MEETING_FOLDERS.earlbear).toBe('👥 EarlBear/👥 Meetings')
  })

  test('personal note folder', () => {
    expect(NOTE_FOLDERS.personal).toBe('🏡 Personal/🏡📝 Notes')
  })
})
