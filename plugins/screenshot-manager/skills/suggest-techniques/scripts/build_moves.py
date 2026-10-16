#!/usr/bin/env python3
"""Turn classification verdicts and the approved picks into move_files.py and
update_manifest.py inputs, so approvals never need hand-written JSON.

Verdicts file: a TSV with one line per candidate, keyed by the "n" from list_candidates.py:
    n<TAB>label<TAB>score<TAB>mechanism<TAB>title<TAB>reason
Keep it as the running table while classifying; it survives a context reset.

Usage:
    python3 build_moves.py --candidates candidates.json --verdicts verdicts.tsv \\
        --pick 6,7,12 --dest "<techniques folder>" --out-dir /tmp/suggest-techniques
    python3 build_moves.py ... --summary          # print the score-sorted table, write nothing

Writes <out-dir>/moves.json and <out-dir>/entries.json.
Output (JSON on stdout): {"moves": N, "entries": N, "unknown_picks": [...]}
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path


def load_verdicts(path: Path) -> dict[int, dict]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            n, label, score, mechanism, title, reason = (row + [""] * 6)[:6]
            out[int(n)] = {"label": label, "score": int(score or 0), "mechanism": mechanism,
                           "title": title, "reason": reason}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--pick", default="", help="comma-separated n values the user approved")
    ap.add_argument("--dest", help="techniques folder (required unless --summary)")
    ap.add_argument("--out-dir", default="/tmp/suggest-techniques")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()

    cands = {c["n"]: c for c in json.loads(Path(args.candidates).read_text(encoding="utf-8"))}
    verdicts = load_verdicts(Path(args.verdicts))
    missing = sorted(set(cands) - set(verdicts))

    if args.summary:
        rows = sorted((cands[n] | verdicts[n] for n in verdicts if n in cands), key=lambda r: (-r["score"], r["n"]))
        for r in rows:
            print(f"{r['n']:>3}  {r['taken'][5:16]}  {r['group']}  {r['label']:<20} {r['score']}  "
                  f"{r['mechanism']:<12} {r['title']}")
        print(dict(Counter(v["label"] for v in verdicts.values())), f"unclassified: {missing}")
        return 0

    if not args.dest:
        raise SystemExit("--dest is required")
    picks = [int(x) for x in args.pick.split(",") if x.strip()]
    unknown = [n for n in picks if n not in cands or n not in verdicts]
    moves, entries = [], []
    for n in picks:
        if n in unknown:
            continue
        c, v = cands[n], verdicts[n]
        moves.append({"src": c["path"], "dest_dir": args.dest})
        entries.append({"file": c["name"], "taken": c["taken"], "group": c["group"], **v})
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "moves.json").write_text(json.dumps(moves, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "entries.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"moves": len(moves), "entries": len(entries), "unknown_picks": unknown}, indent=2))
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
