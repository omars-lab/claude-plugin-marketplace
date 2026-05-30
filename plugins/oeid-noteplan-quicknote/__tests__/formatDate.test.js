// script.js uses DataStore as a global — stub it before requiring
global.DataStore = { folders: [] }
global.Editor = {}
global.CommandBar = {}

const { formatDate } = require('../script.js')

describe('formatDate', () => {
  const RealDate = Date

  function mockDate(isoString) {
    global.Date = class extends RealDate {
      constructor(...args) { return args.length ? new RealDate(...args) : new RealDate(isoString) }
      static now() { return new RealDate(isoString).getTime() }
    }
  }

  afterEach(() => { global.Date = RealDate })

  test('yymmdd with daysAgo=0 formats today correctly', () => {
    mockDate('2026-04-22T12:00:00Z')
    expect(formatDate(0, 'yymmdd')).toBe('260422')
  })

  test('yymmdd with daysAgo=3 subtracts days', () => {
    mockDate('2026-04-22T12:00:00Z')
    expect(formatDate(3, 'yymmdd')).toBe('260419')
  })

  test('iso format returns YYYY-MM-DD', () => {
    mockDate('2026-04-22T12:00:00Z')
    expect(formatDate(0, 'iso')).toBe('2026-04-22')
  })

  test('week format returns YYYY-Www', () => {
    mockDate('2026-04-22T12:00:00Z')
    // 2026-04-22 is in ISO week 17
    expect(formatDate(0, 'week')).toBe('2026-W17')
  })

  test('week format pads single-digit weeks', () => {
    mockDate('2026-01-05T12:00:00Z')
    // 2026-01-05 is in ISO week 02
    expect(formatDate(0, 'week')).toBe('2026-W02')
  })
})
