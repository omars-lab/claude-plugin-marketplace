#!/usr/bin/env python3
"""
records.py -- the one writer and the one validator for consumer research records.

Two record kinds, both append-only CSV:

  evidence   one row per (candidate, criterion) score, with its grade and source
  listings   one row per marketplace listing

Usage:
    records.py init   --kind evidence --file evidence.csv
    records.py append --kind evidence --file evidence.csv --set candidate="M3" --set score=4 ...
    records.py check  --file evidence.csv

Append-only CSV, not a JSON array, because research fans out to parallel
subagents. Every subagent appending one line to a shared file is safe: a single
short write to a file opened O_APPEND does not interleave. Rewriting a JSON
array from several agents at once silently loses whichever findings lost the
race, and the loss is invisible -- you get a smaller matrix, not an error.

Every validation rule lives HERE and nowhere else. record.sh is a thin argument
translator; the PostToolUse hook calls `check`. If a rule needs to change, it
changes once.
"""

import argparse
import csv
import io
import os
import re
import sys

# A line has to stay comfortably under PIPE_BUF (4096) for the append to be
# atomic. Fields get truncated toward that; a row that still blows past it is
# an error rather than a silent corruption of somebody else's row.
MAX_LINE = 3500

SCHEMAS = {
    "evidence": {
        "columns": ["retrieved", "candidate", "criterion", "score", "grade",
                    "value", "source_url", "note"],
        "required": ["retrieved", "candidate", "criterion", "score", "grade"],
    },
    "listings": {
        "columns": ["retrieved", "price", "status", "date", "condition", "variant",
                    "bundle", "location", "shipping", "source", "url", "title", "notes"],
        "required": ["retrieved", "price", "status", "condition", "source", "url"],
    },
}

ENUMS = {
    "grade": ["A", "B", "C", "D"],
    "status": ["sold", "asking", "auction_end"],
    "condition": ["parts", "fair", "good", "excellent", "like_new", "new_open_box"],
    "shipping": ["local", "shipped", "unknown"],
}

# Attacker-controlled free text. Truncate rather than reject -- a seller writing
# an essay is not a validation failure, it is just a long listing.
MAXLEN = {"title": 200, "notes": 400, "note": 400, "value": 120,
          "candidate": 120, "criterion": 120, "location": 120, "bundle": 200}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(value):
    """Flatten to one safe line. Newlines and tabs become spaces; controls go."""
    s = str(value)
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    s = CTRL_RE.sub("", s)
    # A leading =, +, - or @ makes a spreadsheet treat the cell as a formula.
    # These files get opened in Excel and Sheets; prefix-quote to keep text text.
    if s[:1] in ("=", "+", "-", "@"):
        s = "'" + s
    return s.strip()


def check_row(kind, row, where=""):
    """Return a list of human-readable problems with one record. Empty == valid."""
    schema = SCHEMAS[kind]
    problems = []
    loc = f"{where}: " if where else ""

    unknown = [k for k in row if k not in schema["columns"]]
    if unknown:
        problems.append(f"{loc}unknown column(s): {', '.join(sorted(unknown))}")

    for field in schema["required"]:
        if not str(row.get(field, "")).strip():
            problems.append(f"{loc}{field} is required")

    for field, allowed in ENUMS.items():
        v = str(row.get(field, "")).strip()
        if v and v not in allowed:
            problems.append(f"{loc}{field}='{v}' -- must be one of: {', '.join(allowed)}")

    for field in ("retrieved", "date"):
        v = str(row.get(field, "")).strip()
        if v and not DATE_RE.match(v):
            problems.append(f"{loc}{field}='{v}' -- must be YYYY-MM-DD")

    if kind == "evidence":
        v = str(row.get("score", "")).strip()
        if v:
            try:
                if not 1 <= float(v) <= 5:
                    raise ValueError
            except ValueError:
                problems.append(f"{loc}score='{v}' -- must be a number from 1 to 5")

        # The honesty rules, made mechanical. A grade is a claim about where a
        # number came from; A/B/C all claim an external source, so they have to
        # name it. D claims no source at all, so it has to show its reasoning --
        # an ungrounded, unexplained D is how a matrix fills up with vibes.
        grade = str(row.get("grade", "")).strip().upper()
        url = str(row.get("source_url", "")).strip()
        note = str(row.get("note", "")).strip()
        if grade in ("A", "B", "C"):
            if not url:
                problems.append(
                    f"{loc}grade {grade} needs source_url -- "
                    f"{'measured' if grade == 'A' else 'reviewed' if grade == 'B' else 'reported'} "
                    "by whom, where?")
            elif not url.startswith(("http://", "https://")):
                problems.append(f"{loc}source_url='{url[:60]}' -- must be an http(s) URL")
        elif grade == "D" and not note:
            problems.append(f"{loc}grade D needs a note -- inferred from what?")

    if kind == "listings":
        v = str(row.get("price", "")).strip().replace(",", "").lstrip("$")
        if v:
            try:
                if float(v) <= 0:
                    raise ValueError
            except ValueError:
                problems.append(f"{loc}price='{v}' -- must be a positive number, digits only")
        url = str(row.get("url", "")).strip()
        if url and not url.startswith(("http://", "https://")):
            problems.append(f"{loc}url='{url[:60]}' -- must be an http(s) URL. "
                            "Every listing links to itself or it is an assertion, not evidence.")

    return problems


def render(kind, row):
    """Validate and return the record as one properly-quoted CSV line."""
    problems = check_row(kind, row)
    if problems:
        raise SystemExit("records.py: refusing to write --\n  " + "\n  ".join(problems))

    out = {}
    for col in SCHEMAS[kind]["columns"]:
        v = clean(row.get(col, ""))
        limit = MAXLEN.get(col)
        if limit and len(v) > limit:
            v = v[:limit].rstrip() + " [truncated]"
        out[col] = v

    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=SCHEMAS[kind]["columns"],
                   lineterminator="\n").writerow(out)
    line = buf.getvalue()
    if len(line.encode("utf-8")) > MAX_LINE:
        raise SystemExit(
            f"records.py: row is {len(line.encode('utf-8'))} bytes, over the {MAX_LINE} "
            "limit that keeps parallel appends atomic. Shorten the note or title.")
    return line


def kind_of(path):
    """Infer the record kind from an existing file's header."""
    with open(path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), None)
    if header is None:
        raise SystemExit(f"records.py: {path} is empty -- run `records.py init` first")
    for kind, schema in SCHEMAS.items():
        if header == schema["columns"]:
            return kind
    raise SystemExit(
        f"records.py: {path} header does not match any known record kind.\n"
        f"  found:    {','.join(header)}\n"
        + "\n".join(f"  {k}: {','.join(v['columns'])}" for k, v in SCHEMAS.items()))


def cmd_init(args):
    if os.path.exists(args.file) and os.path.getsize(args.file) > 0:
        found = kind_of(args.file)
        if found != args.kind:
            raise SystemExit(f"records.py: {args.file} already exists as a '{found}' file")
        print(f"records.py: {args.file} already initialized ({found})")
        return
    os.makedirs(os.path.dirname(os.path.abspath(args.file)), exist_ok=True)
    with open(args.file, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerow(SCHEMAS[args.kind]["columns"])
    print(f"records.py: initialized {args.file} ({args.kind})")


def cmd_append(args):
    row = {}
    for pair in args.set:
        if "=" not in pair:
            raise SystemExit(f"records.py: --set expects key=value, got '{pair}'")
        k, v = pair.split("=", 1)
        row[k.strip()] = v

    if not os.path.exists(args.file):
        raise SystemExit(
            f"records.py: {args.file} does not exist. Run `records.py init --kind "
            f"{args.kind or 'evidence'} --file {args.file}` once before fanning out, "
            "so parallel writers never race to create the header.")

    kind = args.kind or kind_of(args.file)
    if args.kind and kind_of(args.file) != args.kind:
        raise SystemExit(f"records.py: {args.file} is a '{kind_of(args.file)}' file, "
                         f"not '{args.kind}'")

    line = render(kind, row)
    # O_APPEND: the whole short line lands in one place, or not at all.
    fd = os.open(args.file, os.O_WRONLY | os.O_APPEND)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    print(f"records.py: +1 {kind} row -> {args.file}")


def cmd_check(args):
    kind = kind_of(args.file)
    problems, n = [], 0
    with open(args.file, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            n += 1
            row = {k: v for k, v in row.items() if k is not None}
            problems += check_row(kind, row, where=f"line {i}")

    if problems:
        print(f"records.py: {args.file} ({kind}, {n} rows) -- "
              f"{len(problems)} problem(s):", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        sys.exit(1)
    print(f"records.py: {args.file} OK -- {kind}, {n} rows")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="create the file with its header row")
    pi.add_argument("--kind", required=True, choices=sorted(SCHEMAS))
    pi.add_argument("--file", required=True)
    pi.set_defaults(func=cmd_init)

    pa = sub.add_parser("append", help="validate one record and append it")
    pa.add_argument("--kind", choices=sorted(SCHEMAS))
    pa.add_argument("--file", required=True)
    pa.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    pa.set_defaults(func=cmd_append)

    pc = sub.add_parser("check", help="validate every row in a file")
    pc.add_argument("--file", required=True)
    pc.set_defaults(func=cmd_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
