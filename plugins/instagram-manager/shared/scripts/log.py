"""log.py — one greppable line per event, for every instagram-manager script.

    from log import log, log_to
    log_to("/path/to/run.log")          # optional: also append to a file
    log("import", saves=8000, out="x")  # 2026-01-01T00:00:00Z pid=123 ev=import saves=8000 out=x

Keys and values carry no spaces; a value with a space (or an empty one) is quoted, so free text
goes in msg="...". Lines go to stderr, so a script's real output on stdout stays clean.
"""

import datetime as dt
import os
import sys

_fh = None


def log_to(path):
    """Also append every line to this file (its folder is created)."""
    global _fh
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    _fh = open(path, "a", encoding="utf-8")


def log(ev, **kv):
    parts = [dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), f"pid={os.getpid()}", f"ev={ev}"]
    for k, v in kv.items():
        v = str(v).replace('"', "'").replace("\n", " ")
        parts.append(f'{k}="{v}"' if (" " in v or not v) else f"{k}={v}")
    line = " ".join(parts)
    print(line, file=sys.stderr)
    if _fh:
        _fh.write(line + "\n")
        _fh.flush()
