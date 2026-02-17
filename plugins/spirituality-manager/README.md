# Spirituality Manager Plugin

Plan and track spiritual practices including Ramadan worship schedules, Quran memorization (hifz), and dua routines.

## Skills

### `/plan-ramadan`

Plan your Ramadan ibadah schedule with daily worship goals, meal planning considerations, and progress tracking.

**Usage:**
```
/plan-ramadan
```

### `/plan-hifz`

Plan and track Quran memorization with structured revision schedules, new memorization targets, and progress tracking.

**Usage:**
```
/plan-hifz
```

### `/plan-dua`

Organize duas for different occasions and build a daily dua practice with rotation schedules and categorization.

**Usage:**
```
/plan-dua
```

## Installation

```bash
claude plugin install /path/to/oeid-claude-plugin-marketplace/plugins/spirituality-manager
```

## Architecture

```
spirituality-manager/
├── .claude-plugin/
│   └── plugin.json
├── README.md
└── skills/
    ├── plan-ramadan/
    │   └── SKILL.md
    ├── plan-hifz/
    │   └── SKILL.md
    └── plan-dua/
        └── SKILL.md
```

## License

MIT

## Author

Omar Eid (with Claude Code assistance)
