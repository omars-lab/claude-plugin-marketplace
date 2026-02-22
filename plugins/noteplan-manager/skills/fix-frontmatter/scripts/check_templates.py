#!/usr/bin/env python3
"""
check_templates.py — Validate NotePlan @Templates/ EJS frontmatter blocks.

Template files have two sections:
  1. `---` outer block: NotePlan metadata (title, type: empty-note)
  2. `--` inner block: EJS frontmatter template — declares fields that will
     populate the created note's `---` frontmatter at instantiation time.

This script validates:
  - Outer --- block exists with correct title and type fields
  - Inner -- EJS block exists and declares all required fields for its schema
  - No unknown fields (warns)
  - EJS placeholder syntax looks plausible (e.g., <%- fieldName %>)

Usage:
    python3 check_templates.py [<templates_dir>] [--format json|human]

Default templates_dir: NotePlan @Templates/ directory.

Exit codes:
    0 = all templates valid
    1 = issues found
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


def check_template_file(filepath: str) -> dict | None:
    """
    Check a single template file. Returns result dict (always — templates should be correct).
    Returns None only if file is unreadable.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return {'file': filepath, 'error': str(e), 'issues': []}

    result = fm_lib.parse_template(text, filepath=filepath)

    return {
        'file': filepath,
        'outer_fields': result.outer_fields,
        'ejs_fm_fields': result.ejs_fm_fields,
        'issues': result.issues,
    }


def collect_template_files(templates_dir: str) -> list[str]:
    """Return all .md files in the templates directory (non-recursive)."""
    if not os.path.isdir(templates_dir):
        return []
    return sorted(
        os.path.join(templates_dir, f)
        for f in os.listdir(templates_dir)
        if f.endswith('.md') and not f.startswith('.')
    )


def format_human(results: list[dict]) -> str:
    lines = ['check_templates — NotePlan @Templates/ EJS frontmatter validation',
             '=' * 60]

    issues_found = [r for r in results if r.get('issues')]
    lines.append(f'Templates checked: {len(results)}  with issues: {len(issues_found)}')

    for r in results:
        if r.get('error'):
            lines.append(f"\n✗ {r['file']}")
            lines.append(f"  ERROR: {r['error']}")
            continue

        if not r.get('issues'):
            lines.append(f"  ✓ {os.path.basename(r['file'])}")
            lines.append(f"    outer: {r.get('outer_fields', {})}  fields: {r.get('ejs_fm_fields', [])}")
            continue

        lines.append(f"\n✗ {r['file']}")
        lines.append(f"  outer: {r.get('outer_fields', {})}  fields: {r.get('ejs_fm_fields', [])}")
        for issue in r['issues']:
            t = issue['type']
            if t == 'missing_outer_block':
                lines.append(f"  ✗ missing --- outer metadata block")
            elif t == 'bad_outer_type':
                lines.append(f"  ✗ outer block: {issue['reason']}")
            elif t == 'missing_ejs_fm_block':
                lines.append(f"  ✗ missing -- inner EJS frontmatter block")
            elif t == 'missing_field_in_template':
                lines.append(f"  ✗ missing required field in -- block: '{issue['field']}' (schema: {issue.get('schema')})")
            elif t == 'unknown_field_in_template':
                lines.append(f"  ⚠ unknown field in -- block: '{issue['field']}' (may be intentional)")
            else:
                lines.append(f"  ✗ {issue}")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Validate NotePlan @Templates/ EJS frontmatter blocks.')
    parser.add_argument('templates_dir', nargs='?', default=DEFAULT_TEMPLATES_DIR,
                        help='Path to @Templates/ directory')
    parser.add_argument('--format', choices=['json', 'human'], default='human')
    args = parser.parse_args()

    files = collect_template_files(args.templates_dir)
    if not files:
        print(f'No template files found in: {args.templates_dir}')
        sys.exit(0)

    results = []
    for fp in files:
        result = check_template_file(fp)
        if result:
            results.append(result)

    if args.format == 'json':
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_human(results))

    has_issues = any(
        any(i.get('type') != 'unknown_field_in_template' for i in r.get('issues', []))
        for r in results
    )
    sys.exit(1 if has_issues else 0)


if __name__ == '__main__':
    main()
