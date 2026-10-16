#!/usr/bin/env python3
"""batch_review.py — how the batch agents did, and whether the batches should be bigger or smaller.

    batch_review.py                       every agent run found, then a size suggestion per kind
    batch_review.py --kind tag            only the save-tagger runs (tag, locate or frames)
    batch_review.py --budget 100000       the most context one agent should reach (default 120,000 tokens)
    batch_review.py --transcripts DIR     another folder of Claude Code session transcripts

Reads   ~/.claude/projects/<the data repo's path, / as ->/*/subagents/agent-*.jsonl
            the Claude Code transcript of each agent the session started; only numbers are taken
            from it: the batch path in its prompt, tokens, times, error kinds. No caption, answer or
            message text is printed or kept.
        $INSTAGRAM_HOME/.cache/batches/<kind>/merged.jsonl
            one line per merged batch (tag_saves.py --merge, resolve_post_location.py --merge,
            read_frames.py --merge): saves, chars, and the saves it missed
Writes  nothing; a table on stdout, a summary line on stderr

An agent run is one transcript whose prompt names a batch file under .cache/batches/<kind>/. It is
matched to the first merge of that batch after the agent finished (within 12 hours), which gives
its saves and the saves it missed. A run with no merge row is shown with its saves unknown.

The suggestion fits peak context ≈ base + per_char × batch characters over the runs of one kind
(saves, for frames, whose agents look at pictures), then gives the batch size that keeps an agent
under the budget. With fewer than 2 sizes to compare it says so and suggests nothing.
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
from home import cache, home  # noqa: E402
from log import log  # noqa: E402

KINDS = ("tag", "locate", "frames")
BATCH = re.compile(r"Batch:\s*(\S+?/batches/(tag|locate|frames)/(batch-\d+)\.json)")
AGENT = re.compile(r"agents/([\w-]+)\.md")
MERGE_WINDOW = dt.timedelta(hours=12)
BUDGET = 120000
# The size knob each kind has, and its default (tag_saves.py, resolve_post_location.py, read_frames.py).
KNOB = {"tag": ("chars", "--batch-chars", 60000), "locate": ("chars", "--batch-chars", 60000),
        "frames": ("saves", "--batch-saves", 6)}


def default_transcripts():
    slug = re.sub(r"[^A-Za-z0-9]", "-", home())
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", slug)


def when(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def texts(content):
    """The plain text parts of a message's content."""
    if isinstance(content, str):
        return [content]
    return [c.get("text") or "" for c in content or [] if isinstance(c, dict) and c.get("type") == "text"]


def result_chars(content):
    if isinstance(content, str):
        return len(content)
    return sum(len(c.get("text") or "") for c in content or [] if isinstance(c, dict))


def parse(path):
    """One agent run's numbers, or None when the transcript is not a batch agent's."""
    run = None
    usage, stamps, errors, read_ids = {}, [], [], set()
    model, read_chars, wrote = None, 0, False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("timestamp"):
                stamps.append(when(row["timestamp"]))
            msg = row.get("message") or {}
            content = msg.get("content")
            if row.get("type") == "user" and run is None:
                for t in texts(content):
                    m = BATCH.search(t)
                    if m:
                        a = AGENT.search(t)
                        run = {"batch_file": m.group(1), "kind": m.group(2), "batch": m.group(3),
                               "agent": a.group(1) if a else ""}
                        break
            if row.get("isApiErrorMessage"):
                errors.append(str(row.get("error") or "api_error"))
            if row.get("type") == "assistant":
                model = model or msg.get("model")
                u = msg.get("usage") or {}
                if u:
                    usage[row.get("requestId") or len(usage)] = u
            for c in content if isinstance(content, list) else []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    fp = str((c.get("input") or {}).get("file_path") or "")
                    if run and c.get("name") == "Read" and fp == run["batch_file"]:
                        read_ids.add(c.get("id"))
                    if c.get("name") == "Write" and fp.endswith(".answers.json"):
                        wrote = True
                elif c.get("type") == "tool_result" and c.get("tool_use_id") in read_ids:
                    read_chars += result_chars(c.get("content"))
    if not run:
        return None
    ctx = [u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
           for u in usage.values()]
    stamps = [s for s in stamps if s]
    run.update({
        "transcript": os.path.basename(path), "model": model or "",
        "start": min(stamps) if stamps else None, "end": max(stamps) if stamps else None,
        "turns": len(usage), "peak": max(ctx) if ctx else 0,
        "out": sum(u.get("output_tokens", 0) for u in usage.values()),
        "read_chars": read_chars, "wrote": wrote, "errors": sorted(set(errors)),
    })
    return run


def find_runs(folder):
    paths = sorted(set(glob.glob(os.path.join(folder, "*", "subagents", "agent-*.jsonl"))
                       + glob.glob(os.path.join(folder, "subagents", "agent-*.jsonl"))
                       + glob.glob(os.path.join(folder, "agent-*.jsonl"))))
    runs = [r for r in (parse(p) for p in paths) if r]
    return sorted(runs, key=lambda r: r["end"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc))


def load_merges(kind):
    path = cache("batches", kind, "merged.jsonl")
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                row["at"] = when(row.get("at"))
                rows.append(row)
    return rows


def join(runs, merges):
    """Give each run the first unused merge of its batch after it ended."""
    used = set()
    for r in runs:
        r["merge"] = None
        if not r["end"]:
            continue
        for i, m in enumerate(merges.get(r["kind"]) or []):
            if (r["kind"], i) in used or m.get("batch") != r["batch"] or not m["at"]:
                continue
            # merge rows are stamped to the second; the transcript to the millisecond
            if r["end"] - dt.timedelta(seconds=2) <= m["at"] <= r["end"] + MERGE_WINDOW:
                used.add((r["kind"], i))
                r["merge"] = m
                break
    return runs


def missed(m):
    if not m:
        return None
    return m.get("missing", m.get("unanswered"))


def size(r, by):
    m = r["merge"] or {}
    if by == "saves":
        return m.get("saves")
    return m.get("chars") or r["read_chars"] or None


def fit(points):
    """Least squares for peak = base + k × size; None with fewer than 2 sizes."""
    xs = [x for x, _ in points]
    if len(set(xs)) < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(y for _, y in points)
    k = sum((x - mx) * (y - my) for x, y in points) / sum((x - mx) ** 2 for x in xs)
    return my - k * mx, k


def suggest(kind, runs, budget):
    """A line saying what batch size keeps an agent under the budget, and why."""
    by, flag, now = KNOB[kind]
    points = [(size(r, by), r["peak"]) for r in runs if size(r, by) and r["peak"] and not r["errors"]]
    if not points:
        return f"{kind}: no runs to judge by", None
    line = fit(points)
    if not line or line[1] <= 0:
        top = max(points, key=lambda p: p[1])
        return (f"{kind}: {len(points)} runs, all near one size ({top[0]:,} {by}); peak context {top[1]:,} of a"
                f" {budget:,} budget. Too few sizes to fit; vary {flag} next round to learn more."), None
    base, k = line
    best = int((budget - base) / k)
    step = 5000 if by == "chars" else 1
    best = max(step, best // step * step)
    gaps = sum(missed(r["merge"]) or 0 for r in runs if r["merge"])
    saves = sum((r["merge"] or {}).get("saves") or 0 for r in runs)
    verdict = "bigger" if best > now else "smaller" if best < now else "the same"
    text = (f"{kind}: peak context ≈ {base:,.0f} + {k:,.2f} per {by[:-1]} over {len(points)} runs. Under"
            f" {budget:,} tokens a batch can hold about {best:,} {by} ({flag}; now {now:,}), so {verdict}."
            f" Missed saves: {gaps} of {saves}.")
    if by == "chars":
        # A chars batch also stops at --batch-saves; say which limit the runs met, and the saves that fit.
        per_save = [size(r, "chars") / r["merge"]["saves"] for r in runs
                    if r["merge"] and r["merge"].get("saves") and size(r, "chars")]
        if per_save:
            fits = int(best / statistics.median(per_save))
            text += (f" At {statistics.median(per_save):,.0f} chars a save, that is about {fits} saves"
                     f" (--batch-saves; now 40).")
    return text, best


def fmt_row(r):
    m = r["merge"]
    return [r["kind"], r["end"].strftime("%Y-%m-%d %H:%M") if r["end"] else "?", r["batch"], r["model"],
            str(m.get("saves")) if m else "?",
            f"{m['chars']:,}" if m and m.get("chars") else (f"~{r['read_chars']:,}" if r["read_chars"] else "?"),
            f"{r['peak']:,}", f"{r['out']:,}", str(r["turns"]),
            f"{(r['end'] - r['start']).total_seconds() / 60:.1f}" if r["start"] else "?",
            "?" if missed(m) is None else str(missed(m)),
            ",".join(r["errors"]) or ("no answers" if not r["wrote"] else "")]


HEAD = ["kind", "finished (UTC)", "batch", "model", "saves", "chars", "peak context", "output", "turns",
        "minutes", "missed", "problem"]


def table(rows):
    widths = [max(len(str(c)) for c in col) for col in zip(HEAD, *rows)]
    out = [" | ".join(h.ljust(w) for h, w in zip(HEAD, widths)), "-+-".join("-" * w for w in widths)]
    out += [" | ".join(str(c).ljust(w) for c, w in zip(row, widths)) for row in rows]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kind", choices=KINDS, help="only this kind of batch")
    ap.add_argument("--budget", type=int, default=BUDGET, help="most context tokens one agent should reach")
    ap.add_argument("--transcripts", default=None, help="folder of session transcripts (default: this data repo's)")
    args = ap.parse_args(argv)
    folder = args.transcripts or default_transcripts()
    kinds = [args.kind] if args.kind else list(KINDS)
    runs = [r for r in find_runs(folder) if r["kind"] in kinds]
    runs = join(runs, {k: load_merges(k) for k in kinds})
    if not runs:
        print(f"no batch agent runs found under {folder}")
        log("batch_review", runs=0, folder=folder)
        return 0
    print(table([fmt_row(r) for r in runs]))
    print()
    for k in kinds:
        mine = [r for r in runs if r["kind"] == k]
        if mine:
            print(suggest(k, mine, args.budget)[0])
    problems = [r for r in runs if r["errors"] or not r["wrote"] or (missed(r["merge"]) or 0) > 0
                or r["peak"] > args.budget]
    if problems:
        print(f"\nlook at: {len(problems)} runs hit an error, wrote no answers, missed saves or went over the budget"
              f" ({', '.join(r['transcript'] for r in problems[:8])}{' …' if len(problems) > 8 else ''})")
    log("batch_review", runs=len(runs), merged=sum(1 for r in runs if r["merge"]), problems=len(problems),
        folder=folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
