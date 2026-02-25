#!/usr/bin/env python3
"""
fix_frontmatter.py — Fix frontmatter in place, then re-validate.

Usage:
    python3 fix_frontmatter.py <file_or_dir> [--dry-run] [--recursive] [--format json|human]

Per-file workflow:
    1. Parse → validate → collect issues
    2. Apply fixes (infer missing fields, correct delimiter)
    3. Write corrected frontmatter back to file (skip if --dry-run)
    4. Re-validate → report remaining unfixable issues

Exit codes:
    0 = all files fixed (or had no issues)
    1 = some unfixable issues remain
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import frontmatter as fm_lib


def fix_file(filepath: str, dry_run: bool) -> dict:
    """
    Fix frontmatter in a single file.
    Returns a result dict (always, even if no changes needed).
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return {'file': filepath, 'error': str(e), 'success': False}

    fm = fm_lib.parse(text, filepath=filepath)

    # Skip EJS template files — they contain EJS source code, not real note frontmatter
    if fm.is_ejs_template:
        return {'file': filepath, 'skipped': True, 'reason': 'EJS template file (@Templates/)', 'success': True}

    # Skip files with no frontmatter
    if fm.delimiter is None:
        return {'file': filepath, 'skipped': True, 'reason': 'no frontmatter', 'success': True}

    vr_before = fm_lib.validate(fm, filepath)

    # Nothing to fix?
    if vr_before.valid:
        return {'file': filepath, 'changes': [], 'remaining_issues': [], 'success': True}

    fix_result = fm_lib.fix(fm, filepath)

    # Determine output delimiter (always --- after fix)
    out_delimiter = '---'

    # Rebuild file text: new frontmatter + body
    new_fm_text = fm_lib.render(fix_result.fields, delimiter=out_delimiter)
    new_text = new_fm_text + fm.body

    if not dry_run:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_text)
        except OSError as e:
            return {'file': filepath, 'error': str(e), 'success': False}

    # Re-validate with the fixed frontmatter
    fm_after = fm_lib.parse(new_text)
    vr_after = fm_lib.validate(fm_after, filepath)

    # Collect remaining issues
    remaining = []
    for f in vr_after.missing:
        remaining.append({'type': 'missing_field', 'field': f,
                          'reason': 'cannot infer — add manually'})
    for field, reason in vr_after.bad_values.items():
        if field == 'delimiter':
            continue
        remaining.append({'type': 'bad_value', 'field': field, 'reason': reason})
    # Also surface unfixable from fix()
    for f in fix_result.unfixable:
        if not any(r.get('field') == f for r in remaining):
            remaining.append({'type': 'missing_field', 'field': f,
                              'reason': 'cannot infer — no emoji in filename or parent folder'})

    return {
        'file': filepath,
        'dry_run': dry_run,
        'changes': fix_result.changes,
        'remaining_issues': remaining,
        'success': not remaining,
    }


def collect_files(path: str, recursive: bool) -> list[str]:
    if os.path.isfile(path):
        return [path]

    files = []
    if recursive:
        for root, dirs, filenames in os.walk(path):
            dirs[:] = [d for d in dirs if d != '@Trash']
            for name in filenames:
                if name.endswith('.md'):
                    files.append(os.path.join(root, name))
    else:
        for name in os.listdir(path):
            if name.endswith('.md'):
                full = os.path.join(path, name)
                if os.path.isfile(full):
                    files.append(full)

    return sorted(files)


def format_human(results: list[dict], dry_run: bool) -> str:
    lines = []
    mode = ' (DRY RUN — no files written)' if dry_run else ''
    lines.append(f'fix_frontmatter{mode}')
    lines.append('=' * 50)

    changed = [r for r in results if r.get('changes')]
    skipped = [r for r in results if r.get('skipped')]
    failed  = [r for r in results if r.get('error')]
    unfixed = [r for r in results if r.get('remaining_issues')]

    lines.append(f'Files processed: {len(results) - len(skipped)}  skipped: {len(skipped)}  errors: {len(failed)}')
    lines.append(f'Files changed:   {len(changed)}  with remaining issues: {len(unfixed)}')

    for r in results:
        if r.get('skipped') or (not r.get('changes') and not r.get('remaining_issues')):
            continue
        lines.append(f"\n{r['file']}")
        for ch in r.get('changes', []):
            action = ch.get('action', '?')
            field  = ch.get('field', '?')
            value  = ch.get('value', '')
            src    = ch.get('inferred_from', '')
            if field == 'delimiter':
                lines.append(f"  ✓ fixed delimiter: {ch.get('from')} → {ch.get('to')}")
            else:
                lines.append(f"  ✓ {action} {field}: {value}  (from: {src})")
        for ri in r.get('remaining_issues', []):
            lines.append(f"  ✗ {ri['type']} [{ri.get('field', '?')}]: {ri.get('reason', '')}")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Fix NotePlan frontmatter.')
    parser.add_argument('path', help='File or directory to fix')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    parser.add_argument('--recursive', action='store_true', help='Recurse into subdirectories')
    parser.add_argument('--format', choices=['json', 'human'], default='human')
    args = parser.parse_args()

    files = collect_files(args.path, args.recursive)
    results = []
    for fp in files:
        result = fix_file(fp, dry_run=args.dry_run)
        # Only include in output if something happened
        if result.get('changes') or result.get('remaining_issues') or result.get('error'):
            results.append(result)

    if args.format == 'json':
        # For JSON output: only emit files with changes or issues
        out = [r for r in results if not r.get('skipped')]
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(format_human(results, args.dry_run))

    has_issues = any(r.get('remaining_issues') or r.get('error') for r in results)
    sys.exit(1 if has_issues else 0)


if __name__ == '__main__':
    main()
