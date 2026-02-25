"""
frontmatter.py — Core library for parsing, validating, and fixing NotePlan frontmatter.

Imported by check_frontmatter.py and fix_frontmatter.py.

## Template file nuance (important)

NotePlan template files (`@Templates/*.md`) have a two-section structure:

    ---                          ← outer block: NotePlan template metadata (title, type)
    title: 🏢📆 Work Plan        ← standard YAML consumed by NotePlan
    type: empty-note
    ---
    <% prompt('field', ...) %>   ← EJS source code
    --                           ← inner block: EJS frontmatter template
    doctype: 📆
    status: <%- status %>        ← EJS placeholder — not real YAML values
    --
    # <%- fullTitle %>

The `--` inner block is EJS *source code* that generates frontmatter in the created note.
Template files should be SKIPPED entirely — they are not note files to validate or fix.

Real note files (created from templates) always use `---` delimiters with static YAML values.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FrontmatterResult:
    delimiter: Optional[str]   # '---', '--', or None (None = no frontmatter)
    fields: dict               # parsed key-value pairs
    body: str                  # everything after frontmatter block
    raw_fm: str                # raw frontmatter text (without delimiters)
    is_ejs_template: bool      # True if this is a @Templates/ file with -- EJS block
                               # (these should be skipped, not validated or fixed)


@dataclass
class ValidationResult:
    valid: bool
    missing: list          # required fields not present
    bad_values: dict       # field: reason
    warnings: list         # non-fatal issues
    schema: str            # detected schema name


@dataclass
class FixResult:
    fields: dict           # corrected fields
    changes: list          # [{field, action, value, inferred_from}]
    unfixable: list        # fields that need user input


@dataclass
class TemplateParseResult:
    outer_fields: dict     # fields from the --- outer metadata block (title, type)
    ejs_fm_fields: list    # field names declared in the -- EJS inner block (keys only)
    ejs_fm_raw: str        # raw text of the -- inner EJS block
    issues: list           # validation issues found


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

# Status emojis that are valid values
STATUS_EMOJIS = {'🔮', '🚦', '🟢', '🟡', '🔴', '❎', '✅'}

# Required fields per schema
SCHEMA_REQUIRED = {
    'work_plan':     ['doctype', 'status', 'started', 'namespace', 'workstream'],
    'personal_plan': ['doctype', 'status', 'started', 'namespace', 'plantype'],
    'meeting':       ['doctype', 'started', 'namespace'],
    'idea':          ['doctype', 'started', 'namespace'],
    'thought':       ['doctype', 'started', 'namespace', 'plantype'],
    'question':      ['doctype', 'asked'],
    'ejs_template':  [],   # skipped entirely — EJS source files
    'unknown':       [],
}

# Date format per schema field
SCHEMA_DATE_FORMATS = {
    'work_plan':     {'started': 'YYYY-MM-DD'},
    'personal_plan': {'started': 'YYMMDD'},
    'meeting':       {'started': 'YYMMDD'},
    'idea':          {'started': 'YYMMDD'},
    'thought':       {'started': 'YYMMDD'},
    'question':      {'asked': 'YYYY-MM-DD'},
}

# Doctype emoji → schema prefix
DOCTYPE_SCHEMA_MAP = {
    '📆': 'plan',
    '🗒️': 'meeting',
    '💡': 'idea',
    '🧠': 'thought',
    '❓': 'question',
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _has_ejs(text: str) -> bool:
    return bool(re.search(r'<%', text))


def parse(text: str, filepath: str = '') -> FrontmatterResult:
    """
    Parse frontmatter from note text.

    Template files (`@Templates/*.md`) have two sections:
      1. `---` outer block: NotePlan metadata (title, type) — skip, not note frontmatter
      2. `--` inner block: EJS source template — skip, this is code not YAML

    For template files: returns is_ejs_template=True, delimiter=None so callers skip them.

    For real notes: detects `---` (standard) or `--` (bad delimiter to fix).
    """
    is_template_file = '@Templates' in filepath

    # Template files: parse outer --- to confirm it's a template, then bail out
    if is_template_file:
        # Confirm it has the NotePlan template metadata outer block
        m = re.match(r'^---\n(.*?)\n---\n?(.*)', text, re.DOTALL)
        if m:
            outer_fm = m.group(1)
            outer_fields = _parse_yaml_simple(outer_fm)
            if 'type' in outer_fields and outer_fields.get('type') in ('empty-note', 'template'):
                # This is a NotePlan template file — skip entirely
                return FrontmatterResult(None, outer_fields, m.group(2), outer_fm,
                                         is_ejs_template=True)
        # If no recognized outer block, fall through to regular parsing
        # but still mark as template
        return FrontmatterResult(None, {}, text, '', is_ejs_template=True)

    # Real note files: try --- (correct) first
    m = re.match(r'^---\n(.*?)\n---\n?(.*)', text, re.DOTALL)
    if m:
        raw_fm = m.group(1)
        body = m.group(2)
        fields = _parse_yaml_simple(raw_fm)
        return FrontmatterResult('---', fields, body, raw_fm, is_ejs_template=False)

    # Try -- (double dash — bad delimiter in a real note, needs fixing)
    m = re.match(r'^--\n(.*?)\n--\n?(.*)', text, re.DOTALL)
    if m:
        raw_fm = m.group(1)
        body = m.group(2)
        fields = _parse_yaml_simple(raw_fm)
        return FrontmatterResult('--', fields, body, raw_fm, is_ejs_template=False)

    # No frontmatter
    return FrontmatterResult(None, {}, text, '', is_ejs_template=False)


def parse_template(text: str, filepath: str = '') -> TemplateParseResult:
    """
    Parse a @Templates/ file to extract and validate its EJS frontmatter block.

    Template structure:
        ---                          ← outer block (NotePlan metadata, stripped at instantiation)
        title: ...
        type: empty-note
        ---
        <% EJS code %>               ← prompt() calls and variable setup
        --                           ← inner block (becomes the note's --- frontmatter)
        doctype: 📆
        status: <%- status %>        ← EJS placeholder
        started: <%- started %>
        namespace: 🏢
        workstream: <%- workstream %>
        --

    Returns a TemplateParseResult with:
        - outer_fields: dict from the --- block (title, type)
        - ejs_fm_fields: list of field names declared in the -- block (keys only, not EJS values)
        - ejs_fm_raw: raw text of the -- block
        - issues: list of validation issues (missing/extra/unexpected fields)
    """
    outer_fields = {}
    ejs_fm_fields = []
    ejs_fm_raw = ''
    issues = []

    # Parse outer --- block
    m = re.match(r'^---\n(.*?)\n---\n?(.*)', text, re.DOTALL)
    if not m:
        issues.append({'type': 'missing_outer_block',
                       'reason': 'No --- outer metadata block found'})
        return TemplateParseResult(outer_fields, ejs_fm_fields, ejs_fm_raw, issues)

    outer_fm_text = m.group(1)
    rest = m.group(2)
    outer_fields = _parse_yaml_simple(outer_fm_text)

    # Check outer block has required template metadata
    if outer_fields.get('type') not in ('empty-note', 'template'):
        issues.append({'type': 'bad_outer_type',
                       'reason': f"type should be 'empty-note', got: {outer_fields.get('type')}"})

    # Find the -- inner block (EJS frontmatter template)
    m2 = re.search(r'^--\n(.*?)\n--', rest, re.DOTALL | re.MULTILINE)
    if not m2:
        issues.append({'type': 'missing_ejs_fm_block',
                       'reason': 'No -- inner EJS frontmatter block found'})
        return TemplateParseResult(outer_fields, ejs_fm_fields, ejs_fm_raw, issues)

    ejs_fm_raw = m2.group(1)

    # Extract field names from EJS block (ignore EJS values, just get keys)
    for line in ejs_fm_raw.splitlines():
        stripped = line.strip()
        if ':' in stripped and not stripped.startswith('<%'):
            key = stripped.split(':')[0].strip()
            if key:
                ejs_fm_fields.append(key)

    # Detect expected schema from filename.
    # Check specific note types before generic plan check (e.g. "Personal Idea" has 📆 in name).
    basename = os.path.basename(filepath)
    if 'Idea' in basename or '💡' in basename:
        expected_schema = 'idea'
    elif 'Thought' in basename or '🧠' in basename:
        expected_schema = 'thought'
    elif 'Question' in basename or '❓' in basename:
        expected_schema = 'question'
    elif 'Meeting' in basename or '📝' in basename:
        expected_schema = 'meeting'
    elif 'Work Plan' in basename or ('🏢' in basename and '📆' in basename):
        expected_schema = 'work_plan'
    elif 'Personal Plan' in basename or ('🏡' in basename and '📆' in basename):
        expected_schema = 'personal_plan'
    else:
        expected_schema = 'unknown'

    required = SCHEMA_REQUIRED.get(expected_schema, [])

    # Validate that all required fields are declared in the EJS -- block
    for req_field in required:
        if req_field not in ejs_fm_fields:
            issues.append({'type': 'missing_field_in_template',
                           'field': req_field,
                           'reason': f'Required field "{req_field}" not declared in -- EJS block',
                           'schema': expected_schema})

    # Check for fields not in any known schema (warn only)
    all_known = set(f for schema_fields in SCHEMA_REQUIRED.values() for f in schema_fields)
    for declared in ejs_fm_fields:
        if declared not in all_known:
            issues.append({'type': 'unknown_field_in_template',
                           'field': declared,
                           'reason': f'Field "{declared}" not in any known schema (may be intentional)',
                           'schema': expected_schema})

    return TemplateParseResult(outer_fields, ejs_fm_fields, ejs_fm_raw, issues)


def _parse_yaml_simple(text: str) -> dict:
    """
    Minimal YAML key: value parser (single-level only).
    Preserves insertion order.
    """
    result = {}
    for line in text.splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            result[key.strip()] = val.strip()
    return result


# ---------------------------------------------------------------------------
# Schema detection
# ---------------------------------------------------------------------------

def detect_schema(fields: dict, filepath: str) -> str:
    """
    Returns schema name: 'work_plan', 'personal_plan', 'meeting',
    'idea', 'thought', 'question', 'ejs_template', 'unknown'.

    Template files return 'ejs_template' — they should be skipped by callers.
    """
    # Template files — EJS source, not real note frontmatter
    if '@Templates' in filepath:
        return 'ejs_template'

    doctype = fields.get('doctype', '')
    namespace = fields.get('namespace', '')

    if doctype == '📆':
        if namespace == '🏢':
            return 'work_plan'
        if namespace == '🏡':
            return 'personal_plan'
        # Infer from path
        if '🏢' in filepath or 'ServiceNow' in filepath:
            return 'work_plan'
        if '🏡' in filepath or 'Personal' in filepath:
            return 'personal_plan'
        return 'work_plan'  # default for plan files

    if doctype == '🗒️':
        return 'meeting'
    if doctype == '💡':
        return 'idea'
    if doctype == '🧠':
        return 'thought'
    if doctype == '❓':
        return 'question'

    # Infer from filename prefix
    # (os already imported at module level)
    basename = os.path.basename(filepath)
    if basename.startswith('🏢📆') or basename.startswith('🏢🟢') or basename.startswith('🏢🔮'):
        return 'work_plan'
    if basename.startswith('🏡📆'):
        return 'personal_plan'
    if basename.startswith('🗒️') or basename.startswith('🏢🗒️'):
        return 'meeting'
    if basename.startswith('💡'):
        return 'idea'
    if basename.startswith('🧠'):
        return 'thought'
    if basename.startswith('❓'):
        return 'question'

    return 'unknown'


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_YYMMDD_RE = re.compile(r'^\d{6}$')
_ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def validate(fm: FrontmatterResult, filepath: str) -> ValidationResult:
    """
    Validate frontmatter against the appropriate schema.

    Template files (`@Templates/*.md`): skipped entirely (is_ejs_template=True).
    Files with no frontmatter: returns valid=True with schema='none'.
    Real notes: validates required fields, delimiter (must be ---), date formats.
    """
    # EJS template files — skip entirely, not note frontmatter
    if fm.is_ejs_template:
        return ValidationResult(True, [], {}, [], 'ejs_template')

    if fm.delimiter is None:
        return ValidationResult(True, [], {}, [], 'none')

    schema = detect_schema(fm.fields, filepath)
    required = SCHEMA_REQUIRED.get(schema, [])
    date_formats = SCHEMA_DATE_FORMATS.get(schema, {})

    missing = []
    bad_values = {}
    warnings = []

    # Check required fields exist
    for f in required:
        if f not in fm.fields or not fm.fields[f]:
            missing.append(f)

    # Validate delimiter — real notes must use ---
    if fm.delimiter != '---':
        bad_values['delimiter'] = f'found "{fm.delimiter}", expected "---"'

    # Validate date formats
    for date_field, fmt in date_formats.items():
        if date_field in fm.fields and fm.fields[date_field]:
            val = fm.fields[date_field]
            if fmt == 'YYYY-MM-DD' and not _ISO_DATE_RE.match(val):
                bad_values[date_field] = f'expected YYYY-MM-DD, got "{val}"'
            elif fmt == 'YYMMDD' and not _YYMMDD_RE.match(val):
                bad_values[date_field] = f'expected YYMMDD (6 digits), got "{val}"'

    # Validate status if present
    if 'status' in fm.fields and fm.fields['status']:
        val = fm.fields['status']
        if val not in STATUS_EMOJIS:
            bad_values['status'] = f'"{val}" is not a valid status emoji ({", ".join(sorted(STATUS_EMOJIS))})'

    valid = not missing and not bad_values
    return ValidationResult(valid, missing, bad_values, warnings, schema)


# ---------------------------------------------------------------------------
# Fixing
# ---------------------------------------------------------------------------

def fix(fm: FrontmatterResult, filepath: str) -> FixResult:
    """
    Infer and fix missing/bad frontmatter fields.

    Skips EJS value fields (is_template=True).
    Returns unfixable list for fields needing user input.
    """
    # (os already imported at module level)

    fields = dict(fm.fields)  # copy
    changes = []
    unfixable = []

    schema = detect_schema(fields, filepath)
    vr = validate(fm, filepath)

    # EJS template files — skip entirely
    if fm.is_ejs_template:
        return FixResult(fields, changes, unfixable)

    # Fix delimiter (always fix -- → ---)
    if fm.delimiter == '--':
        changes.append({'field': 'delimiter', 'action': 'fixed', 'from': '--', 'to': '---'})
        # delimiter fix is applied at render time via the delimiter parameter

    basename = os.path.basename(filepath)
    dirname = os.path.dirname(filepath)
    parent_folder = os.path.basename(dirname)

    # --- Infer namespace ---
    if 'namespace' not in fields or not fields['namespace']:
        if '🏢' in filepath or 'ServiceNow' in filepath:
            fields['namespace'] = '🏢'
            changes.append({'field': 'namespace', 'action': 'added', 'value': '🏢',
                            'inferred_from': 'path contains ServiceNow/🏢'})
        elif '🏡' in filepath or 'Personal' in filepath:
            fields['namespace'] = '🏡'
            changes.append({'field': 'namespace', 'action': 'added', 'value': '🏡',
                            'inferred_from': 'path contains Personal/🏡'})
        else:
            unfixable.append('namespace')

    # --- Infer doctype ---
    if 'doctype' not in fields or not fields['doctype']:
        # Try to extract from filename first emoji
        doctype_emoji = _extract_doctype_from_filename(basename)
        if doctype_emoji:
            fields['doctype'] = doctype_emoji
            changes.append({'field': 'doctype', 'action': 'added', 'value': doctype_emoji,
                            'inferred_from': f'filename prefix emoji'})
        else:
            unfixable.append('doctype')

    # --- Infer workstream (work plans) ---
    if schema == 'work_plan' and ('workstream' not in fields or not fields['workstream']):
        ws = _extract_first_emoji(parent_folder)
        if ws:
            fields['workstream'] = ws
            changes.append({'field': 'workstream', 'action': 'added', 'value': ws,
                            'inferred_from': f'parent folder: {parent_folder}'})
        else:
            # Try filename 3rd emoji
            ws = _extract_nth_emoji(basename, 3)
            if ws:
                fields['workstream'] = ws
                changes.append({'field': 'workstream', 'action': 'added', 'value': ws,
                                'inferred_from': f'filename 3rd emoji'})
            else:
                unfixable.append('workstream')

    # --- Infer plantype (personal plans / thoughts) ---
    if schema in ('personal_plan', 'thought') and ('plantype' not in fields or not fields['plantype']):
        pt = _extract_nth_emoji(basename, 3)
        if pt:
            fields['plantype'] = pt
            changes.append({'field': 'plantype', 'action': 'added', 'value': pt,
                            'inferred_from': 'filename 3rd emoji'})
        else:
            pt = _extract_first_emoji(parent_folder)
            if pt:
                fields['plantype'] = pt
                changes.append({'field': 'plantype', 'action': 'added', 'value': pt,
                                'inferred_from': f'parent folder: {parent_folder}'})
            else:
                unfixable.append('plantype')

    # --- Infer started / asked ---
    date_field = 'asked' if schema == 'question' else 'started'
    if date_field not in fields or not fields[date_field]:
        date_val = _extract_date_from_filename(basename)
        if date_val:
            # Format depends on schema
            if schema == 'work_plan':
                formatted = _yymmdd_to_iso(date_val)
                fields[date_field] = formatted
                changes.append({'field': date_field, 'action': 'added', 'value': formatted,
                                'inferred_from': f'filename date {date_val} → YYYY-MM-DD'})
            else:
                fields[date_field] = date_val
                changes.append({'field': date_field, 'action': 'added', 'value': date_val,
                                'inferred_from': 'filename YYMMDD pattern'})
        else:
            if schema == 'question':
                today = datetime.now().strftime('%Y-%m-%d')
                fields['asked'] = today
                changes.append({'field': 'asked', 'action': 'added', 'value': today,
                                'inferred_from': "today's date (no date in filename)"})
            else:
                unfixable.append(date_field)

    # --- Infer status (work_plan, personal_plan) ---
    if schema in ('work_plan', 'personal_plan') and ('status' not in fields or not fields['status']):
        # Try to read from H1 title in body
        status = _extract_status_from_body(fm.body)
        if status:
            fields['status'] = status
            changes.append({'field': 'status', 'action': 'added', 'value': status,
                            'inferred_from': 'H1 title 2nd emoji'})
        else:
            unfixable.append('status')

    # --- Fix bad date formats ---
    for date_field_key, expected_fmt in SCHEMA_DATE_FORMATS.get(schema, {}).items():
        if date_field_key in fields and fields[date_field_key]:
            val = fields[date_field_key]
            if _has_ejs(str(val)):
                continue
            if expected_fmt == 'YYYY-MM-DD' and _YYMMDD_RE.match(val):
                # Convert YYMMDD → YYYY-MM-DD
                iso = _yymmdd_to_iso(val)
                fields[date_field_key] = iso
                changes.append({'field': date_field_key, 'action': 'fixed',
                                'value': iso, 'inferred_from': f'converted from YYMMDD {val}'})
            elif expected_fmt == 'YYMMDD' and _ISO_DATE_RE.match(val):
                # Convert YYYY-MM-DD → YYMMDD
                yymmdd = val[2:4] + val[5:7] + val[8:10]
                fields[date_field_key] = yymmdd
                changes.append({'field': date_field_key, 'action': 'fixed',
                                'value': yymmdd, 'inferred_from': f'converted from ISO {val}'})

    return FixResult(fields, changes, unfixable)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render(fields: dict, delimiter: str = '---') -> str:
    """
    Serialize fields dict back to frontmatter string (with surrounding delimiters).
    """
    lines = [delimiter]
    for key, val in fields.items():
        lines.append(f'{key}: {val}')
    lines.append(delimiter)
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Broad emoji regex covering most Unicode emoji ranges
_EMOJI_RE = re.compile(
    r'[\U0001F300-\U0001F9FF'
    r'\U00002600-\U000027BF'
    r'\U0001FA00-\U0001FA9F'
    r'\U00002300-\U000023FF'
    r'\uFE0F\u200D]+'
)

def _extract_first_emoji(text: str) -> Optional[str]:
    """Return the first emoji sequence found in text."""
    m = _EMOJI_RE.search(text)
    return m.group(0) if m else None


def _extract_nth_emoji(text: str, n: int) -> Optional[str]:
    """Return the nth emoji (1-indexed) found in text."""
    matches = list(_EMOJI_RE.finditer(text))
    if len(matches) >= n:
        return matches[n - 1].group(0)
    return None


_YYMMDD_PATTERN = re.compile(r'(\d{6})')

def _extract_date_from_filename(basename: str) -> Optional[str]:
    """Extract YYMMDD date string from filename."""
    m = _YYMMDD_PATTERN.search(basename)
    return m.group(1) if m else None


def _yymmdd_to_iso(yymmdd: str) -> str:
    """Convert YYMMDD to YYYY-MM-DD (assumes 20xx century)."""
    yy = yymmdd[0:2]
    mm = yymmdd[2:4]
    dd = yymmdd[4:6]
    return f'20{yy}-{mm}-{dd}'


def _extract_doctype_from_filename(basename: str) -> Optional[str]:
    """Detect doctype emoji from filename prefix."""
    if basename.startswith('📆') or '📆' in basename[:6]:
        return '📆'
    if basename.startswith('🗒️') or '🗒️' in basename[:6]:
        return '🗒️'
    if basename.startswith('💡'):
        return '💡'
    if basename.startswith('🧠'):
        return '🧠'
    if basename.startswith('❓'):
        return '❓'
    # Namespace prefix then doctype
    if '📆' in basename[:12]:
        return '📆'
    if '🗒️' in basename[:12]:
        return '🗒️'
    return None


def _extract_status_from_body(body: str) -> Optional[str]:
    """
    Read H1 title from body, return 2nd emoji if it's a valid status emoji.
    """
    for line in body.splitlines():
        if line.startswith('# '):
            title = line[2:]
            emojis = list(_EMOJI_RE.finditer(title))
            if len(emojis) >= 2:
                second = emojis[1].group(0)
                if second in STATUS_EMOJIS:
                    return second
            return None
    return None
