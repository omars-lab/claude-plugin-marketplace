"""claude.py — the Anthropic key, one model call, and the word-for-word quote check.

    from claude import load_key, call_claude, call_tool, parse_json, quote_ok, Refused
    key = load_key()                                   # ANTHROPIC_API_KEY, else LastPass
    text = call_claude(key, system, user_msg)          # retries 429/5xx, logs model_start/done
    d = call_tool(key, system, user_msg, tool)         # the answer as fields, through a forced tool call
    d = parse_json(text)                               # first {...} in the reply
    quote_ok(d["quote"], caption)                      # the quote is really in the caption
    USAGE                                              # calls and tokens so far, for a run's total
    Refused                                            # raised for no credit or a bad key: stop the run

The key comes from ANTHROPIC_API_KEY, or a LastPass secure note whose body is the key, or JSON
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
    note = out.stdout.strip()
    if note.startswith("{"):  # a JSON note: {"api_key": "..."}
        return json.loads(note)["api_key"]
    return note  # a note that holds only the key


class Refused(Exception):
    """The API turned the account down (no credit, bad key): every later call would fail too."""


def _post(key, body):
    """One Messages API call, retrying 429/5xx. Returns the response JSON."""
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(3):
        log("model_start", attempt=attempt, model=body["model"])
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                out = json.load(r)
            log("model_done", tokens_in=out["usage"]["input_tokens"], tokens_out=out["usage"]["output_tokens"],
                stop=out.get("stop_reason"))
            with _usage_lock:
                USAGE["calls"] += 1
                USAGE["tokens_in"] += out["usage"]["input_tokens"]
                USAGE["tokens_out"] += out["usage"]["output_tokens"]
            return out
        except urllib.error.HTTPError as e:
            log("model_error", code=e.code)
            if e.code in (429, 500, 502, 503, 529):
                pass
            else:
                try:
                    msg = json.load(e).get("error", {}).get("message", "")
                except (ValueError, AttributeError):
                    msg = ""
                if e.code in (401, 403) or "credit balance" in msg:
                    raise Refused(f"HTTP {e.code}: {msg}") from None
                raise RuntimeError(f"HTTP {e.code}: {msg}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            log("model_timeout", err=type(e).__name__)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("model call kept failing")


def call_claude(key, system, user_msg, model=MODEL, max_tokens=600):
    """The reply's text."""
    out = _post(key, {"model": model, "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": user_msg}]})
    return "".join(b.get("text", "") for b in out["content"])


def call_tool(key, system, user_msg, tool, model=MODEL, max_tokens=600):
    """The model must answer by calling `tool`; returns the tool's input as a dict. No text to parse,
    so a reply can't come back as prose or with the JSON half written."""
    out = _post(key, {"model": model, "max_tokens": max_tokens, "system": system, "tools": [tool],
                      "tool_choice": {"type": "tool", "name": tool["name"]},
                      "messages": [{"role": "user", "content": user_msg}]})
    if out.get("stop_reason") == "max_tokens":
        raise ValueError(f"reply cut off at {max_tokens} tokens")
    for b in out["content"]:
        if b.get("type") == "tool_use" and isinstance(b.get("input"), dict):
            return b["input"]
    raise ValueError("no tool call in the reply")


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
