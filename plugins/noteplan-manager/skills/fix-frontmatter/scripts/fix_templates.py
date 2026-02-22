#!/usr/bin/env python3
"""
fix_templates.py — Fix NotePlan @Templates/ EJS frontmatter blocks.

Template files have two sections:
  1. `---` outer block: NotePlan metadata (title, type: empty-note)
  2. `--` inner block: EJS frontmatter template with <%- variable %> placeholders

This script fixes:
  - Missing outer --- block fields (title, type)
  - Missing required fields in the -- EJS block
  - Adding placeholder declarations (e.g., `fieldname: <%- fieldname %>`) for missing fields

NOTE: This script adds field stubs — the EJS placeholders must still be
wired to actual prompt() variables by the user. Unfixable stubs are reported.

Usage:
    python3 fix_templates.py [<templates_dir>] [--dry-run] [--format json|human]

Default templates_dir: NotePlan @Templates/ directory.

Exit codes:
    0 = all templates valid (or fixed successfully)
    1 = unfixable issues remain
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import frontmatter as fm_lib

DEFAULT_TEMPLATES_DIR = os.path.expanduser(
    '~/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support'
    '/co.noteplan.NotePlan3/Notes/@Templates'
)


def fix_template_file(filepath: str, dry_run: bool) -> dict:
    """
    Validate and report fixes for a single template file.

    For missing fields in the -- block: reports as unfixable (need EJS wiring).
    Does NOT auto-modify template files — EJS variable wiring requires human judgment.
    Reports what needs to be done so the user can fix manually or confirm.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return {'file': filepath, 'error': str(e), 'success': False}

    result = fm_lib.parse_template(text, filepath=filepath)

    # Separate structural errors from field warnings
    structural_issues = [i for i in result.issues
                         if i['type'] not in ('unknown_field_in_template',)]
    warnings = [i for i in result.issues
                if i['type'] == 'unknown_field_in_template']

    if not structural_issues:
        return {
            'file': filepath,
            'ejs_fm_fields': result.ejs_fm_fields,
            'changes': [],
            'remaining_issues': warnings,
            'success': True,
        }

    # Template files require manual EJS wiring — report unfixable issues
    # (unlike note files, we can't auto-fix EJS templates without breaking the EJS logic)
    unfixable = []
    for issue in structural_issues:
        t = issue['type']
        if t == 'missing_field_in_template':
            unfixable.append({
                'type': 'unfixable',
                'field': issue['field'],
                'reason': (
                    f"Add '  {issue['field']}: <%- {issue['field']} %>' to the -- block "
                    f"and wire a prompt() call for it. Schema: {issue.get('schema')}"
                ),
            })
        elif t == 'missing_ejs_fm_block':
            unfixable.append({
                'type': 'unfixable',
                'reason': 'No -- inner EJS block found. Add a -- block with required fields.',
            })
        elif t == 'missing_outer_block':
            unfixable.append({
                'type': 'unfixable',
                'reason': 'No --- outer metadata block. Add: ---\\ntitle: <name>\\ntype: empty-note\\n---',
            })
        elif t == 'bad_outer_type':
            unfixable.append({
                'type': 'unfixable',
                'field': 'type',
                'reason': issue['reason'],
            })

    return {
        'file': filepath,
        'ejs_fm_fields': result.ejs_fm_fields,
        'changes': [],
        'remaining_issues': unfixable + warnings,
        'success': not unfixable,
    }


def collect_template_files(templates_dir: str) -> list[str]:
    if not os.path.isdir(templates_dir):
        return []
    return sorted(
        os.path.join(templates_dir, f)
        for f in os.listdir(templates_dir)
        if f.endswith('.md') and not f.startswith('.')
    )


def format_human(results: list[dict], dry_run: bool) -> str:
    lines = ['fix_templates — NotePlan @Templates/ EJS frontmatter validation',
             '=' * 60]
    if dry_run:
        lines[0] += ' (DRY RUN)'

    valid = [r for r in results if r.get('success') and not r.get('remaining_issues')]
    with_issues = [r for r in results if r.get('remaining_issues')]

    lines.append(f'Templates checked: {len(results)}  valid: {len(valid)}  with issues: {len(with_issues)}')
    lines.append('')
    lines.append('NOTE: Template EJS blocks require manual fixes — this script reports')
    lines.append('      what needs to be done but does not auto-modify template files.')
    lines.append('')

    for r in results:
        if r.get('error'):
            lines.append(f"✗ {r['file']}\n  ERROR: {r['error']}")
            continue
        if not r.get('remaining_issues'):
            lines.append(f"✓ {os.path.basename(r['file'])}  fields: {r.get('ejs_fm_fields', [])}")
            continue

        lines.append(f"\n✗ {r['file']}")
        lines.append(f"  Current -- block fields: {r.get('ejs_fm_fields', [])}")
        for ri in r.get('remaining_issues', []):
            t = ri.get('type', '?')
            if t == 'unfixable':
                field = ri.get('field', '')
                prefix = f"[{field}] " if field else ''
                lines.append(f"  ✗ ACTION REQUIRED: {prefix}{ri['reason']}")
            else:
                lines.append(f"  ⚠ {ri}")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Validate and report fixes for NotePlan @Templates/ EJS frontmatter.')
    parser.add_argument('templates_dir', nargs='?', default=DEFAULT_TEMPLATES_DIR,
                        help='Path to @Templates/ directory')
    parser.add_argument('--dry-run', action='store_true',
                        help='Report issues without modifying files (always true for templates)')
    parser.add_argument('--format', choices=['json', 'human'], default='human')
    args = parser.parse_args()

    files = collect_template_files(args.templates_dir)
    if not files:
        print(f'No template files found in: {args.templates_dir}')
        sys.exit(0)

    results = []
    for fp in files:
        result = fix_template_file(fp, dry_run=args.dry_run)
        results.append(result)

    if args.format == 'json':
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_human(results, args.dry_run))

    has_blocking_issues = any(not r.get('success') for r in results)
    sys.exit(1 if has_blocking_issues else 0)


if __name__ == '__main__':
    main()
