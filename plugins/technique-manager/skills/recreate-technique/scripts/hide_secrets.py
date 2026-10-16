#!/usr/bin/env python3
"""Hide passwords, keys and tokens in transcript text before anything prints it.

A transcript holds whatever was pasted into the session: a password typed into a prompt, an
API key in a command, a token in a tool result. The scripts that print parts of transcripts
(search-transcripts snippets, research-backstory excerpts, find_session matches) pass every
piece through hide() first, so a secret never reaches the terminal, a context file or a post.
Each hidden value becomes "[hidden <kind>]"; the label in front of it ("password:") stays, so
the sentence still reads.

It errs on the side of hiding: a random-looking word that is not a secret may be hidden too.
That costs a word in an excerpt; a missed secret costs a rotation.

Audit (the CLI): how many values each rule hides in transcripts, and the outline of any long
random-looking word that still gets through (letters become a/A, digits 9, so the outline shows
the shape and never the value).

    python3 hide_secrets.py FILE_OR_DIR ... [--since 2026-10-08T19:00] [--until 2026-10-08T20:00]

Output (JSON on stdout):
    {"files": N, "lines": N, "hidden": {"<kind>": n}, "suspects": [{"file", "line", "t", "shape"}]}
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Words that label a secret. "token", "key" and "pass" alone are too common in prose and test output
# to count ("PASS:", "passed", "DashPass"); "token" and "key" need a qualifier ("api key", "access_token").
LABEL = (r"(?:password|passwd|passphrase|passcode|pwd|secret|client[_ -]?secret|"
         r"(?:api|access|secret|private|signing|auth)[_ -]?key|apikey|"
         r"(?:access|refresh|auth|bearer|api|session|id)[_ -]?token|credential)s?")

# A value that names where a secret lives instead of being one: an env var, a template, a call.
NOT_A_VALUE = re.compile(r"^(?:\$|<|\{|\[|\(|os\.|process\.|env\b|getenv|None\b|null\b|true\b|false\b|"
                         r"str\b|string\b|int\b|required\b|optional\b|\*+$|•+$|x{4,}$|\.\.\.|…)", re.I)

RULES: list[tuple[str, re.Pattern]] = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.S)),
    ("aws key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("api key", re.compile(r"\bsk-(?:ant-|proj-|live-|test-)?[A-Za-z0-9_-]{20,}")),
    ("google key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe key", re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("shopify token", re.compile(r"\bshp(?:at|ss|ca|pa)_[a-fA-F0-9]{32}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("bearer token", re.compile(r"(?<=\bBearer )[A-Za-z0-9._~+/-]{16,}=*")),
    ("url password", re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)")),
]

# "password: X", "API_KEY=X", "secret is X", "\"password\": \"X\"". The label is a whole word or a
# whole part of a name joined by "_" or "-" (STOREFRONT_PASSWORD, data-api-key), never part of a word.
LABELLED = re.compile(r"(?i)((?<![A-Za-z0-9])(?:[\w-]*[_-])?" + LABEL + r"(?:[_-][\w-]*)?[\"']?\s*"
                      r"([:=]|=>|\bis\b|\bwas\b)\s*[\"']?)([^\s\"',;)\]}]{4,})")
# After "is", "was" or ":", a plain lowercase word is prose ("the password is stored in the keychain").
PROSE = re.compile(r"[a-z]+")

# Words that look made up by a password generator: every kind of character, or a long run of mixed
# letters and digits, with the case flipping as often as a random string flips it. Paths, addresses,
# hex hashes, ids, times, colors, camelCase names and markdown are left alone.
WORD = re.compile(r"[^\s\"'`,;()\[\]{}<>|]{10,}")
HEX_OR_ID = re.compile(r"^(?:[0-9a-f]{7,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
                       r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})$")
# Ids that Claude Code and the API write into every transcript: message, request and tool-call ids.
KNOWN_ID = re.compile(r"^(?:msg|req|toolu|srvtoolu|call|file|chatcmpl|session|run|evt)[_-]\w+$")
NOT_RANDOM = re.compile(r"\d{4}-\d\d-\d\d|\d{1,2}:\d\d|#[0-9a-fA-F]{3,8}\b|\*\*|__|\.\.")
BASE64 = re.compile(r"[A-Za-z0-9+/]{30,}={0,2}")


def case_flips(w: str) -> float:
    """How often the case changes between neighbouring letters: about half the time in a random
    string, rarely in a word, a camelCase name or a constant."""
    pairs = [(a, b) for a, b in zip(w, w[1:]) if a.isalpha() and b.isalpha()]
    return sum(a.islower() != b.islower() for a, b in pairs) / len(pairs) if pairs else 0.0


def looks_random(w: str) -> bool:
    w = w.strip(".:!?*")
    if len(w) < 10 or "://" in w or "@" in w or HEX_OR_ID.match(w) or KNOWN_ID.match(w) or NOT_RANDOM.search(w):
        return False
    lower, upper, digit = (sum(c.islower() for c in w), sum(c.isupper() for c in w), sum(c.isdigit() for c in w))
    mixed = lower >= 3 and upper >= 3 and digit >= 2 and case_flips(w) >= 0.3
    if BASE64.fullmatch(w) and not w.startswith("/") and len(w) <= 200:
        return mixed  # a key in base64 may hold "/" and "+"; a path starts with "/" and reads as words
    if "/" in w or "\\" in w:
        return False
    if re.search(r"\.[a-z]{2,4}$", w) or re.fullmatch(r"[\w.-]+\.[a-z]{2,}", w):  # file names, domains
        return False
    symbol = sum(not c.isalnum() and c not in "-_." for c in w)
    if 12 <= len(w) <= 64 and symbol and mixed:
        return True  # a generated password: every kind of character
    if len(w) >= 20 and mixed:
        return True  # a long random key: mixed case and digits
    return False


def is_value(m: re.Match) -> bool:
    """Whether a LABELLED match holds a value worth hiding, not a pointer to one or a word of prose."""
    sep, value = m.group(2).lower(), m.group(3)
    if value.startswith("[hidden") or NOT_A_VALUE.match(value):
        return False
    return not (sep in (":", "is", "was") and PROSE.fullmatch(value.rstrip(".!?")))


def hide_counted(text: str, found: list | None = None) -> tuple[str, Counter]:
    """The text with each secret replaced by "[hidden <kind>]", and how many of each kind.
    found, if given, gets one (kind, outline) per hidden value: the shape, never the value."""
    seen: Counter = Counter()
    if not text:
        return text, seen

    def sub(kind):
        def f(m):
            seen[kind] += 1
            if found is not None:
                found.append((kind, shape(m.group(0))))
            return f"[hidden {kind}]"
        return f

    for kind, rx in RULES:
        text = rx.sub(sub(kind), text)

    def labelled(m):
        if not is_value(m):
            return m.group(0)
        seen["labelled secret"] += 1
        if found is not None:
            found.append(("labelled secret", shape(m.group(3))))
        return m.group(1) + "[hidden labelled secret]"
    text = LABELLED.sub(labelled, text)

    def word(m):
        if looks_random(m.group(0)):
            seen["random-looking word"] += 1
            if found is not None:
                found.append(("random-looking word", shape(m.group(0))))
            return "[hidden random-looking word]"
        return m.group(0)
    text = WORD.sub(word, text)
    return text, seen


def hide(text: str) -> str:
    return hide_counted(text)[0]


def shape(w: str) -> str:
    """The outline of a word with its value gone: a/A for letters, 9 for digits, symbols as #."""
    return "".join("a" if c.islower() else "A" if c.isupper() else "9" if c.isdigit() else "#" for c in w)


def strings(node):
    """Every string a script could print. A thinking block's signature and an image's data are
    encoded blobs that nothing prints, so they are skipped."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            if k not in ("signature", "data"):
                yield from strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v)


def audit(paths: list[Path], since: str | None, until: str | None, show_hidden: bool = False) -> dict:
    files = sorted({p for path in paths for p in ([path] if path.is_file() else path.rglob("*.jsonl"))})
    hidden: Counter = Counter()
    hidden_shapes: Counter = Counter()
    labelled_shapes: Counter = Counter()
    suspects, lines = [], 0
    for f in files:
        with f.open(encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = rec.get("timestamp") or ""
                if (since and t < since) or (until and t > until):
                    continue
                lines += 1
                for s in strings(rec.get("message") or rec.get("content") or ""):
                    out, seen = hide_counted(s)
                    hidden.update(seen)
                    if show_hidden and seen["random-looking word"]:
                        hidden_shapes.update(shape(w) for w in WORD.findall(s) if looks_random(w))
                    if show_hidden and seen["labelled secret"]:
                        # The label is a key name, safe to show; the value shows only as its outline.
                        labelled_shapes.update(f"{m.group(1).strip()} {shape(m.group(3))[:24]}"
                                               for m in LABELLED.finditer(s) if is_value(m))
                    # What a looser rule would still call random: long, mixed, not yet hidden.
                    for w in re.findall(r"[^\s\"'`,;()\[\]{}<>|/\\]{12,}", out):
                        if w.startswith("[hidden") or HEX_OR_ID.match(w) or KNOWN_ID.match(w):
                            continue
                        kinds = sum(bool(re.search(p, w)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^\w.-]"))
                        if kinds >= 3 and not re.search(r"[a-z]{5}", w):
                            suspects.append({"file": f.name, "line": n, "t": t, "shape": shape(w)})
    out = {"files": len(files), "lines": lines, "hidden": dict(hidden), "suspects": suspects[:200]}
    if show_hidden:
        out["hidden_shapes"] = dict(hidden_shapes.most_common(60))
        out["labelled_shapes"] = dict(labelled_shapes.most_common(60))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="transcript files or folders")
    ap.add_argument("--since", help="only records at or after this ISO time")
    ap.add_argument("--until", help="only records at or before this ISO time")
    ap.add_argument("--show-hidden", action="store_true",
                    help="also list the outlines of the random-looking words it hid, to spot over-hiding")
    args = ap.parse_args()
    print(json.dumps(audit([Path(p).expanduser() for p in args.paths], args.since, args.until, args.show_hidden),
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
