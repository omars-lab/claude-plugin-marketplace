#!/usr/bin/env python3
"""Validate extracted URLs: HEAD-check reachability and complete truncated URLs.

For each URL:
  1. Classify as complete or partial using heuristics
  2. Send HTTP HEAD to confirm reachability (follows redirects)
  3. For partial / unreachable URLs: search via Chrome DevTools Protocol (CDP)
     to find the full URL — falls back to DuckDuckGo if Chrome is unavailable

Chrome CDP notes:
  - Chrome must be running with: --remote-debugging-port=9222
  - On macOS you can launch it with:
      /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
        --remote-debugging-port=9222 --no-first-run --no-default-browser-check
  - Requires: pip install websocket-client

DuckDuckGo fallback uses their public Instant Answer JSON API (no key needed).

Usage:
    # Pipe URLs one per line
    echo "https://example.com/partial..." | python3 validate_urls.py

    # From JSON output of extract_urls.py
    python3 validate_urls.py --json-input /tmp/extracted.json

    # Direct arguments
    python3 validate_urls.py --urls "https://url1" "https://url2..."

Output (JSON list, one entry per unique input URL):
    [
      {
        "url":               "https://original.com/partial...",
        "is_partial":        true,
        "head_status":       null,
        "head_reachable":    false,
        "head_final_url":    null,
        "completed_url":     "https://original.com/full/path/to/page",
        "completion_method": "chrome_cdp",   # or "ddg", "head_redirect", "none"
        "verdict":           "completed"     # valid | partial | completed | unreachable
      }
    ]

Requirements (in screenshot-ocr conda env):
    pip install websocket-client requests
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Partial URL detection
# ---------------------------------------------------------------------------

# Signs that the URL was truncated by the browser or OCR
_TRUNC_SUFFIX_RE = re.compile(r'(\.\.\.|\u2026|\.{2,})$')
_INCOMPLETE_PCT_RE = re.compile(r'%[0-9A-Fa-f]?$')


def is_likely_partial(url: str) -> bool:
    """Return True if the URL appears to be truncated."""
    if _TRUNC_SUFFIX_RE.search(url):
        return True
    if _INCOMPLETE_PCT_RE.search(url):          # cut off mid-percent-encode
        return True
    # Very long URL ending abruptly in a lowercase letter (common OCR truncation)
    if len(url) > 100 and url[-1].isalpha() and url[-1].islower():
        # Heuristic: long URLs with no path/query terminator are suspicious
        path_part = url.split('?')[0]
        if not path_part.endswith('/') and '.' not in path_part.split('/')[-1]:
            return True
    return False


# ---------------------------------------------------------------------------
# HEAD request
# ---------------------------------------------------------------------------

_HEADERS = {'User-Agent': 'Mozilla/5.0 (screenshot-manager url-validator/1.0)'}


def head_check(url: str, timeout: int = 6) -> dict:
    """Send HEAD request. Returns {status, final_url, reachable, error}."""
    # Strip trailing truncation markers before trying
    clean = _TRUNC_SUFFIX_RE.sub('', url).strip()
    try:
        req = urllib.request.Request(clean, method='HEAD', headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {
                'status': resp.status,
                'final_url': resp.url,
                'reachable': 200 <= resp.status < 400,
                'error': None,
            }
    except Exception as e:
        # Some servers reject HEAD — try GET with no body read
        try:
            req2 = urllib.request.Request(clean, headers=_HEADERS)
            with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                return {
                    'status': resp2.status,
                    'final_url': resp2.url,
                    'reachable': 200 <= resp2.status < 400,
                    'error': None,
                }
        except Exception as e2:
            return {'status': None, 'final_url': None, 'reachable': False, 'error': str(e2)}


# ---------------------------------------------------------------------------
# Chrome CDP completion
# ---------------------------------------------------------------------------

_CDP_BASE = 'http://localhost:9222'
_NAV_TIMEOUT = 8          # seconds to wait for page load
_RESULT_JS = """
(function() {
  // Try modern Google result selectors (they change frequently)
  var selectors = [
    'div.g a[href]', 'div[data-sokoban-container] a[href]',
    '.tF2Cxc a[href]', 'h3 a[href]', 'a[jsname][href]'
  ];
  for (var s of selectors) {
    var els = Array.from(document.querySelectorAll(s));
    var hit = els.find(function(a) {
      return a.href && a.href.startsWith('http') && !a.href.includes('google.com');
    });
    if (hit) return hit.href;
  }
  return null;
})()
"""


def _cdp_available() -> bool:
    try:
        with urllib.request.urlopen(f'{_CDP_BASE}/json', timeout=2) as r:
            json.loads(r.read())
            return True
    except Exception:
        return False


def _cdp_search(query: str) -> str | None:
    """Use Chrome CDP to search Google and return the first organic result URL."""
    try:
        import websocket  # websocket-client
    except ImportError:
        return None

    try:
        # Open a new blank tab
        with urllib.request.urlopen(
            f'{_CDP_BASE}/json/new?about:blank', timeout=4
        ) as r:
            tab = json.loads(r.read())
        ws_url = tab.get('webSocketDebuggerUrl')
        tab_id = tab.get('id')
        if not ws_url:
            return None

        ws = websocket.create_connection(ws_url, timeout=_NAV_TIMEOUT)
        _msg_id = [0]

        def send(method: str, params: dict | None = None) -> dict:
            _msg_id[0] += 1
            ws.send(json.dumps({'id': _msg_id[0], 'method': method, 'params': params or {}}))
            # Read until we get the reply for this id (skip events)
            deadline = time.time() + _NAV_TIMEOUT
            while time.time() < deadline:
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get('id') == _msg_id[0]:
                    return msg
            return {}

        # Enable Page events so we can detect load
        send('Page.enable')

        # Navigate to Google search
        search_url = 'https://www.google.com/search?q=' + urllib.parse.quote(query)
        send('Page.navigate', {'url': search_url})

        # Wait for load event
        deadline = time.time() + _NAV_TIMEOUT
        while time.time() < deadline:
            try:
                ws.settimeout(0.5)
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get('method') == 'Page.loadEventFired':
                    break
            except Exception:
                pass

        time.sleep(1)  # brief settle for JS rendering

        # Extract first result
        result = send('Runtime.evaluate', {'expression': _RESULT_JS, 'returnByValue': True})
        first_url = result.get('result', {}).get('result', {}).get('value')

        ws.close()

        # Close the tab we opened
        try:
            urllib.request.urlopen(f'{_CDP_BASE}/json/close/{tab_id}', timeout=2)
        except Exception:
            pass

        return first_url if isinstance(first_url, str) else None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# DuckDuckGo fallback
# ---------------------------------------------------------------------------

def _ddg_search(query: str) -> str | None:
    """Search DuckDuckGo Instant Answer API; return first AbstractURL or Result."""
    try:
        q = urllib.parse.quote_plus(query)
        req = urllib.request.Request(
            f'https://api.duckduckgo.com/?q={q}&format=json&no_html=1&no_redirect=1',
            headers=_HEADERS,
        )
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read())
        # AbstractURL is the definitive answer page (e.g. Wikipedia)
        if data.get('AbstractURL'):
            return data['AbstractURL']
        # Results list
        results = data.get('Results') or []
        for item in results:
            url = item.get('FirstURL') or item.get('URL')
            if url and url.startswith('http'):
                return url
        # RelatedTopics
        for topic in data.get('RelatedTopics') or []:
            url = topic.get('FirstURL')
            if url and url.startswith('http') and 'duckduckgo' not in url:
                return url
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-URL validation
# ---------------------------------------------------------------------------

def validate(url: str) -> dict:
    partial = is_likely_partial(url)
    head = head_check(url)

    result: dict = {
        'url': url,
        'is_partial': partial,
        'head_status': head['status'],
        'head_reachable': head['reachable'],
        'head_final_url': head['final_url'],
        'completed_url': None,
        'completion_method': 'none',
        'verdict': 'valid',
    }

    # If HEAD found a redirect, note the final URL
    if head['reachable'] and head['final_url'] and head['final_url'] != url:
        result['completed_url'] = head['final_url']
        result['completion_method'] = 'head_redirect'

    if head['reachable'] and not partial:
        result['verdict'] = 'valid'
        return result

    # URL is partial or unreachable — try to find the full URL
    # Build a meaningful search query from the URL
    clean = _TRUNC_SUFFIX_RE.sub('', url).strip()
    # Use the domain + path as the query (strip scheme for readability)
    query = re.sub(r'^https?://', '', clean)

    # Try Chrome CDP first (richer results, uses actual Google)
    completed = None
    method = 'none'

    if _cdp_available():
        completed = _cdp_search(query)
        if completed:
            method = 'chrome_cdp'

    # Fall back to DuckDuckGo
    if not completed:
        completed = _ddg_search(query)
        if completed:
            method = 'ddg'

    if completed:
        result['completed_url'] = completed
        result['completion_method'] = method
        result['verdict'] = 'completed'
    elif head['reachable']:
        result['verdict'] = 'valid'        # reachable but couldn't find better
    else:
        result['verdict'] = 'partial' if partial else 'unreachable'

    return result


# ---------------------------------------------------------------------------
# Input collection
# ---------------------------------------------------------------------------

def collect_urls_from_json(path: str) -> list[str]:
    """Extract all unique URLs from extract_urls.py JSON output."""
    data = json.loads(Path(path).read_text())
    seen: set[str] = set()
    out: list[str] = []
    for file_data in data.values():
        if not isinstance(file_data, dict):
            continue
        for u in file_data.get('urls') or []:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
    return out


def collect_urls_from_stdin() -> list[str]:
    return [ln.strip() for ln in sys.stdin if ln.strip().startswith('http')]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description='Validate and complete extracted URLs')
    src = parser.add_mutually_exclusive_group()
    src.add_argument('--urls', nargs='+', help='URLs to validate directly')
    src.add_argument('--json-input', help='Path to extract_urls.py JSON output')
    parser.add_argument('--timeout', type=int, default=6, help='HEAD request timeout (seconds)')
    args = parser.parse_args()

    if args.urls:
        urls = args.urls
    elif args.json_input:
        urls = collect_urls_from_json(args.json_input)
    elif not sys.stdin.isatty():
        urls = collect_urls_from_stdin()
    else:
        parser.print_help()
        sys.exit(1)

    if not urls:
        print(json.dumps([], ensure_ascii=False))
        return

    results = [validate(u) for u in urls]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
