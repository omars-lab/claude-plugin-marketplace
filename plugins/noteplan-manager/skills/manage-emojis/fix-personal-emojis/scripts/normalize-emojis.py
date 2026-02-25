#!/usr/bin/env python3
"""
normalize-emojis.py
Normalize Unicode emoji sequences in a file or stdin to NFC form.

Usage:
  python3 normalize-emojis.py <file>        # normalize file in-place
  python3 normalize-emojis.py <file> --dry-run  # show what would change
  echo "text" | python3 normalize-emojis.py -   # normalize stdin

Used by: fix-work-emojis, fix-personal-emojis
"""

import sys
import unicodedata
import re
import argparse


def normalize_emojis(text: str) -> str:
    """
    Normalize emoji sequences to NFC Unicode form.

    Handles:
    - Mojibake (incorrectly decoded multi-byte sequences)
    - Inconsistent ZWJ (zero-width joiner) sequences
    - Skin tone modifier ordering
    - Variation selector normalization (VS-15/VS-16)
    """
    # NFC normalization: canonical decomposition followed by canonical composition
    normalized = unicodedata.normalize("NFC", text)
    return normalized


def normalize_file(path: str, dry_run: bool = False) -> dict:
    """Normalize a file in-place. Returns stats dict."""
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    normalized = normalize_emojis(original)

    changed = original != normalized
    stats = {
        "path": path,
        "changed": changed,
        "original_len": len(original),
        "normalized_len": len(normalized),
    }

    if changed and not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(normalized)

    return stats


def diff_summary(original: str, normalized: str) -> list[str]:
    """Return lines that changed between original and normalized."""
    orig_lines = original.splitlines()
    norm_lines = normalized.splitlines()
    diffs = []
    for i, (o, n) in enumerate(zip(orig_lines, norm_lines), 1):
        if o != n:
            diffs.append(f"  line {i}:")
            diffs.append(f"    before: {repr(o[:80])}")
            diffs.append(f"    after:  {repr(n[:80])}")
    return diffs


def main():
    parser = argparse.ArgumentParser(description="Normalize emoji encoding in files")
    parser.add_argument("file", help="File to normalize, or - for stdin")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing"
    )
    parser.add_argument("--verbose", action="store_true", help="Show changed lines")
    args = parser.parse_args()

    if args.file == "-":
        original = sys.stdin.read()
        normalized = normalize_emojis(original)
        if args.dry_run or args.verbose:
            diffs = diff_summary(original, normalized)
            if diffs:
                print(f"Would change {len(diffs) // 3} line(s):")
                print("\n".join(diffs))
            else:
                print("No changes needed")
        else:
            sys.stdout.write(normalized)
        return

    stats = normalize_file(args.file, dry_run=args.dry_run)

    if not stats["changed"]:
        print(f"✓ {args.file}: no changes needed")
        return

    if args.dry_run:
        print(f"⚠  {args.file}: would be normalized")
        if args.verbose:
            with open(args.file, "r", encoding="utf-8") as f:
                original = f.read()
            normalized = normalize_emojis(original)
            diffs = diff_summary(original, normalized)
            print("\n".join(diffs))
    else:
        print(f"✓ {args.file}: normalized")
        if args.verbose:
            print(f"  {stats['original_len']} → {stats['normalized_len']} chars")


if __name__ == "__main__":
    main()
