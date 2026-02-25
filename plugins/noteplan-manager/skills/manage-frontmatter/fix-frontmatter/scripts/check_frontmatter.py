#!/usr/bin/env python3
"""
check_frontmatter.py — Validate frontmatter in a file or directory.

Usage:
    python3 check_frontmatter.py <file_or_dir> [--recursive] [--format json|human]

Exit codes:
    0 = all valid (or no frontmatter to validate)
    1 = issues found
"""

import argparse
import json
import os
import sys

# Allow running from any directory
sys.path.insert(0, os.path.dirname(__file__))
import frontmatter as fm_lib


def check_file(filepath: str) -> dict | None:
    """
    Check a single file. Returns issue dict or None if no issues / no frontmatter.

    Template files (`@Templates/*.md`) are skipped — they contain EJS source,
    not real note frontmatter (their inner `--` block is EJS code, not YAML).
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        return None

    fm = fm_lib.parse(text, filepath=filepath)

    # Skip EJS template files and files with no frontmatter silently
    if fm.is_ejs_template or fm.delimiter is None:
        return None

    vr = fm_lib.validate(fm, filepath)

    issues = []

    # Delimiter issue
    if fm.delimiter != '---':
        issues.append({'type': 'bad_delimiter', 'found': fm.delimiter, 'expected': '---'})

    # Missing required fields
    for f in vr.missing:
        issues.append({'type': 'missing_field', 'field': f})

    # Bad values
    for field, reason in vr.bad_values.items():
        if field == 'delimiter':
            continue  # already reported above
        issues.append({'type': 'bad_value', 'field': field, 'reason': reason})

    if not issues:
        return None

    return {
        'file': filepath,
        'schema': vr.schema,
        'is_ejs_template': fm.is_ejs_template,
        'issues': issues,
    }


def collect_files(path: str, recursive: bool) -> list[str]:
    """Return list of .md files to check."""
    if os.path.isfile(path):
        return [path]

    files = []
    if recursive:
        for root, dirs, filenames in os.walk(path):
            # Skip @Trash
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


def format_human(results: list[dict]) -> str:
    if not results:
        return 'All files valid (or no frontmatter to check).'

    lines = []
    for r in results:
        lines.append(f"\n{r['file']}")
        lines.append(f"  schema: {r['schema']}")
        for issue in r['issues']:
            t = issue['type']
            if t == 'missing_field':
                lines.append(f"  ✗ missing field: {issue['field']}")
            elif t == 'bad_delimiter':
                lines.append(f"  ✗ bad delimiter: found \"{issue['found']}\", expected \"{issue['expected']}\"")
            elif t == 'bad_value':
                lines.append(f"  ✗ bad value [{issue['field']}]: {issue['reason']}")
            else:
                lines.append(f"  ✗ {issue}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Validate NotePlan frontmatter.')
    parser.add_argument('path', help='File or directory to check')
    parser.add_argument('--recursive', action='store_true', help='Recurse into subdirectories')
    parser.add_argument('--format', choices=['json', 'human'], default='human')
    args = parser.parse_args()

    files = collect_files(args.path, args.recursive)
    results = []
    for fp in files:
        result = check_file(fp)
        if result:
            results.append(result)

    if args.format == 'json':
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_human(results))

    sys.exit(1 if results else 0)


if __name__ == '__main__':
    main()
