"""claude.py — the Anthropic key, one model call, and the word-for-word quote check.

    from claude import load_key, call_claude, parse_json, quote_ok
    key = load_key()                                   # ANTHROPIC_API_KEY, else LastPass
    text = call_claude(key, system, user_msg)          # retries 429/5xx, logs model_start/done
    d = parse_json(text)                               # first {...} in the reply
    quote_ok(d["quote"], caption)                      # the quote is really in the caption
    USAGE                                              # calls and tokens so far, for a run's total

The key comes from ANTHROPIC_API_KEY, or a LastPass secure note whose body is JSON
{"api_key": "..."}. The note's path is not in this public plugin: pass it, or set
INSTAGRAM_LPASS_PATH (the data repo's Makefile sets it).

Standard library only.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from log import log

MODEL = "claude-haiku-5-5"
HTTP_TIMEOUT = 60
USAGE = {"calls": 0, "tokens_in": 0, "tokens_out": 0}
_usage_lock = threading.Lock()


def load_key(lpass_path=None):
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    lpass_path = lpass_path or os.environ.get("INSTAGRAM_LPASS_PATH")
    if not lpass_path:
        sys.exit("no Anthropic key: set ANTHROPIC_API_KEY, or INSTAGRAM_LPASS_PATH to a LastPass note")
    try:
        out = subprocess.run(["lpass", "show", "--notes", lpass_path], capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        sys.exit(f"no Anthropic key: set ANTHROPIC_API_KEY or log in to lpass ({type(e).__name__})")
    if out.returncode != 0:
        sys.exit(f"no Anthropic key at LastPass {lpass_path!r}: {out.stderr.strip()}")
    return json.loads(out.stdout)["api_key"]


def call_claude(key, system, user_msg, model=MODEL, max_tokens=600):
    body = json.dumps({"model": model, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": user_msg}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(3):
        log("model_start", attempt=attempt, model=model)
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                out = json.load(r)
            log("model_done", tokens_in=out["usage"]["input_tokens"], tokens_out=out["usage"]["output_tokens"])
            with _usage_lock:
                USAGE["calls"] += 1
                USAGE["tokens_in"] += out["usage"]["input_tokens"]
                USAGE["tokens_out"] += out["usage"]["output_tokens"]
            return "".join(b.get("text", "") for b in out["content"])
        except urllib.error.HTTPError as e:
            log("model_error", code=e.code)
            if e.code not in (429, 500, 502, 503, 529):
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            log("model_timeout", err=type(e).__name__)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("model call kept failing")


def parse_json(text):
    """The first JSON object in a model reply, with any ``` fence stripped."""
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def norm(s):
    """Lower-case, straighten curly quotes, collapse whitespace: the quote-matching rule."""
    s = (s or "").replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_ok(quote, text):
    """True when the quote appears in the text word for word (case, quotes, spacing aside)."""
    return bool(quote and quote.strip()) and norm(quote) in norm(text)
