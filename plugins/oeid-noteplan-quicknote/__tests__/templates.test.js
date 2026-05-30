global.DataStore = { folders: [] }
global.Editor = {}
global.CommandBar = {}

const {
  workPlanFrontmatter,
  personalPlanFrontmatter,
  domainPlanFrontmatter,
  meetingFrontmatter,
  planBody,
  meetingBody,
  noteBody,
  formatDate,
} = require('../script.js')

const RealDate = Date
beforeEach(() => {
  global.Date = class extends RealDate {
    constructor(...args) { return args.length ? new RealDate(...args) : new RealDate('2026-04-22T12:00:00Z') }
    static now() { return new RealDate('2026-04-22T12:00:00Z').getTime() }
  }
})
afterEach(() => { global.Date = RealDate })

describe('workPlanFrontmatter', () => {
  test('includes correct doctype, namespace, workstream', () => {
    const fm = workPlanFrontmatter('🧑🏻‍💻', '🟢', 0)
    expect(fm).toContain('doctype: 📆')
    expect(fm).toContain('namespace: 🏢')
    expect(fm).toContain('workstream: 🧑🏻‍💻')
    expect(fm).toContain('status: 🟢')
    expect(fm).toContain('started: 2026-04-22')
  })

  test('has initiative key', () => {
    expect(workPlanFrontmatter('🎯', '🚦', 0)).toContain('initiative:')
  })
})

describe('personalPlanFrontmatter', () => {
  test('uses plantype key (not workstream)', () => {
    const fm = personalPlanFrontmatter('👨🏻‍💻', '🔮', 0)
    expect(fm).toContain('namespace: 🏡')
    expect(fm).toContain('plantype: 👨🏻‍💻')
    expect(fm).not.toContain('workstream:')
  })
})

describe('domainPlanFrontmatter', () => {
  test('NaqshCoffee plan uses ☕️ namespace', () => {
    const fm = domainPlanFrontmatter('☕️', '🎨', '🟢', 0)
    expect(fm).toContain('namespace: ☕️')
    expect(fm).toContain('workstream: 🎨')
  })

  test('EarlBear plan uses 👥 namespace', () => {
    const fm = domainPlanFrontmatter('👥', '🧑🏻‍💻', '🚦', 0)
    expect(fm).toContain('namespace: 👥')
  })
})

describe('meetingFrontmatter', () => {
  test('uses yymmdd for started (not ISO)', () => {
    const fm = meetingFrontmatter('🏢', 0)
    expect(fm).toContain('started: 260422')
    expect(fm).not.toContain('started: 2026-04-22')
  })

  test('doctype is 🗒️', () => {
    expect(meetingFrontmatter('🏡', 0)).toContain('doctype: 🗒️')
  })
})

describe('planBody', () => {
  test('H1 matches title exactly (Golden Rule)', () => {
    const title = '🏢260422🧑🏻‍💻 Build Plugin'
    const fm = workPlanFrontmatter('🧑🏻‍💻', '🟢', 0)
    const body = planBody(title, fm, 0)
    expect(body).toContain(`# ${title}`)
  })

  test('weekly review checkbox contains wikilink and week ref', () => {
    const title = '🏢260422🧑🏻‍💻 Build Plugin'
    const body = planBody(title, workPlanFrontmatter('🧑🏻‍💻', '🟢', 0), 0)
    expect(body).toContain(`[[${title}]]`)
    expect(body).toMatch(/>\d{4}-W\d{2}/)
  })

  test('includes empty task line', () => {
    const body = planBody('Test', workPlanFrontmatter('🎯', '🟢', 0), 0)
    expect(body).toContain('* [ ]\n')
  })
})

describe('meetingBody', () => {
  test('work meeting has Attendees/Agenda/Notes/Action Items sections', () => {
    const title = '🏢 260422 1-1 Ritesh'
    const body = meetingBody(title, meetingFrontmatter('🏢', 0), 0, true)
    expect(body).toContain('## Attendees')
    expect(body).toContain('## Agenda')
    expect(body).toContain('## Notes')
    expect(body).toContain('## Action Items')
  })

  test('non-work meeting has Notes and Action Items but no Agenda', () => {
    const title = '🏡 260422 Family Sync'
    const body = meetingBody(title, meetingFrontmatter('🏡', 0), 0, false)
    expect(body).toContain('## Notes')
    expect(body).toContain('## Action Items')
    expect(body).not.toContain('## Agenda')
  })

  test('action items checkbox contains wikilink', () => {
    const title = '🏢 260422 1-1 Ritesh'
    const body = meetingBody(title, meetingFrontmatter('🏢', 0), 0, true)
    expect(body).toContain(`[[${title}]]`)
  })
})

describe('noteBody', () => {
  test('uses 📝 doctype', () => {
    expect(noteBody('🏢📝 ServiceNow Quirks', '🏢')).toContain('doctype: 📝')
  })

  test('H1 matches title', () => {
    const title = '🏡📝 Random Thought'
    expect(noteBody(title, '🏡')).toContain(`# ${title}`)
  })
})

describe('getWorkstreams with mocked DataStore', () => {
  const { getWorkstreams } = require('../script.js')

  test('returns immediate subdirs of plan root only', () => {
    global.DataStore = {
      folders: [
        '🏢 ServiceNow/📆 Plans/🧑🏻‍💻 Development',
        '🏢 ServiceNow/📆 Plans/🧑🏻‍💻 Development/🤖 Config Agent',
        '🏢 ServiceNow/📆 Plans/🎯 Impact',
        '🏡 Personal/🏡📆 Plans/Present/👨🏻‍💻 Development',
      ]
    }
    const ws = getWorkstreams('work')
    expect(ws).toContain('🧑🏻‍💻 Development')
    expect(ws).toContain('🎯 Impact')
    expect(ws).not.toContain('🤖 Config Agent') // project subfolder — excluded
    expect(ws).not.toContain('👨🏻‍💻 Development') // wrong domain
  })

  test('returns personal activities from correct root', () => {
    global.DataStore = {
      folders: [
        '🏡 Personal/🏡📆 Plans/Present/👨🏻‍💻 Development',
        '🏡 Personal/🏡📆 Plans/Present/🌱 Growth',
        '🏢 ServiceNow/📆 Plans/🎯 Impact',
      ]
    }
    const acts = getWorkstreams('personal')
    expect(acts).toContain('👨🏻‍💻 Development')
    expect(acts).toContain('🌱 Growth')
    expect(acts).not.toContain('🎯 Impact')
  })

  test('falls back to static list for coffee when no subdirs exist', () => {
    global.DataStore = { folders: [] }
    const ws = getWorkstreams('coffee')
    expect(ws).toContain('🎨 Design')
    expect(ws).toContain('🏪 Site')
    expect(ws).toContain('👨🏻‍💼 Strategy')
    expect(ws).toContain('🖼️ Vision')
  })

  test('falls back to static list for earlbear when no subdirs exist', () => {
    global.DataStore = { folders: [] }
    const ws = getWorkstreams('earlbear')
    expect(ws).toContain('🧑🏻‍💻 Development')
    expect(ws).toContain('👨🏻‍💼 Strategy')
  })
})
