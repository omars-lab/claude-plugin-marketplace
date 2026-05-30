"""
url_enrichment.py — Phase G URL enrichment commands for noteplan-sweep CLI.

Commands
--------
fetch-title           HTTP GET a URL and print its <title> tag.
to-markdown-link      Fetch title and print [title](url).
fetch-metadata        Fetch and print YAML metadata for a URL.
enrich-urls           Replace bare URLs in a file with markdown links.
enrich-research-doc   enrich-urls + update domains: frontmatter.
check-dead-links      HEAD-check all URLs in a file, report dead ones.
archive-url           POST to Wayback Machine and print the archive URL.

All network calls use stdlib only: urllib.request, urllib.parse, html.parser.
"""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib import request as urequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, parse_qs, unquote_plus

import noteplan_sweep.utils as utils

# ---------------------------------------------------------------------------
# Optional Playwright import (for --use-chrome)
# ---------------------------------------------------------------------------
try:
    from playwright.sync_api import sync_playwright as _sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USER_AGENT = "noteplan-sweep/0.1"
DEFAULT_TIMEOUT = 5

# Matches bare URLs and URLs inside markdown links: [text](url)
URL_RE = re.compile(r'https?://[^\s\)\]\'"<>]+')
# Matches a markdown link whose target is a URL: [text](https://...)
MD_LINK_RE = re.compile(r'\[.*?\]\((https?://[^\s\)\]\'"<>]+)\)')

# Internal / Okta-protected domains — skip unless --use-chrome is set
INTERNAL_DOMAINS_RE = re.compile(
    r'https?://[^/\s]*(?:service-now\.com|servicenow\.com|sharepoint\.com|okta\.com'
    r'|code\.devsnc\.com)',
    re.IGNORECASE,
)

# URLs to skip or handle specially (local networks, auth callbacks, binaries, UUIDs)

_SKIP_DOMAIN_RE = re.compile(
    r'https?://[^/\s]*(?:'
    r'service-now\.com|servicenow\.com|sharepoint\.com|okta\.com'
    r'|code\.devsnc\.com'                        # ServiceNow internal GitHub (Okta)
    r'|sage\.amazon\.dev'                        # Amazon internal wiki/Q&A
    r'|code\.amazon\.com'                        # Amazon internal GitHub (CodeBrazil)
    r'|w\.amazon\.com'                           # Amazon internal wiki
    r'|talent\.amazon\.dev'                      # Amazon internal transfer tool
    r'|quip-amazon\.com'                         # Amazon internal Quip (collaboration)
    r'|(?:issues|tiny|sim|broadcast|mcm|apttool|weblab|amzn-wwc)\.amazon\.com'  # Amazon internal tools
    r'|\.corp\.amazon\.com'                      # Amazon internal corp tools (all subdomains)
    r'|radar\.aka\.amazon\.com'                  # Amazon internal Radar
    r'|admin\.shopify\.com'                      # Shopify admin (authenticated)
    r'|amazon\.jobs/en/internal/'               # Amazon internal job postings (path-based)
    r'|\.a2z\.com(?:[:/]|$)'                     # Amazon internal *.a2z.com services
    r'|\.ts\.net(?:[:/]|$)'                      # Tailscale hostnames (*.ts.net)
    r'|noteplan(?:[:/]|$)'                       # NotePlan x-callback-url scheme (https://noteplan/...)
    r'|localhost|attlocal\.net|\.local(?:[:/]|$)'
    r')',
    re.IGNORECASE,
)
# Private IP ranges: 127.x (loopback), 192.168.x.x, 10.x.x.x, 172.16-31.x.x, 100.64-127.x.x (Tailscale CGNAT)
_PRIVATE_IP_RE = re.compile(r'https?://(?:127\.|192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.|100\.(?:6[4-9]|[7-9]\d|1(?:0\d|1\d|2[0-7]))\.)')
_OAUTH_PARAM_RE = re.compile(r'[?&](?:code|state|auth_callback|access_token|id_token)=', re.IGNORECASE)
_IMAGE_EXT_RE = re.compile(r'\.(jpe?g|png|gif|webp|svg|ico|bmp|tiff?|mp4|mov|pdf|zip|tar|gz)(\?|$)', re.IGNORECASE)
_UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
_SEARCH_ENGINE_RE = re.compile(
    r'https?://(?:www\.)?(?P<engine>google|bing|duckduckgo)\.com/(?:search|[?])',
    re.IGNORECASE,
)

def _should_skip_url(url: str) -> bool:
    """Return True if a URL should be skipped entirely for enrichment."""
    if _SKIP_DOMAIN_RE.search(url): return True
    if _PRIVATE_IP_RE.match(url): return True
    if _OAUTH_PARAM_RE.search(url): return True
    if _IMAGE_EXT_RE.search(url): return True
    if _UUID_RE.search(url): return True
    if len(url) > 300: return True
    return False

def _search_engine_label(url: str) -> str | None:
    """Return 'Engine: <decoded query>' if url is a search engine query, else None."""
    m = _SEARCH_ENGINE_RE.match(url)
    if not m:
        return None
    engine = m.group('engine').capitalize()
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        query = (qs.get('q') or qs.get('p') or [''])[0]
        query = unquote_plus(query).strip()
        if query:
            return f"{engine}: {query}"
    except Exception:
        pass
    return f"{engine} search"

_CHROME_PROFILE = Path.home() / "Library/Application Support/Google/Chrome"


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

class _MetaParser(HTMLParser):
    """Extract <title> and selected <meta> tags from an HTML document."""

    def __init__(self):
        super().__init__()
        self.title: str | None = None
        self.description: str | None = None
        self.author: str | None = None
        self.published: str | None = None
        self._in_title = False
        self._title_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
            self._title_buf = []
        elif tag == "meta":
            prop = (a.get("property") or "").lower()
            name = (a.get("name") or "").lower()
            content = a.get("content") or ""

            # description
            if self.description is None:
                if prop == "og:description" or name == "description":
                    self.description = content

            # author
            if self.author is None:
                if prop in ("og:article:author", "article:author") or name == "author":
                    self.author = content

            # published
            if self.published is None:
                if prop in ("og:article:published_time", "article:published_time") or name == "date":
                    self.published = content

    def handle_endtag(self, tag: str):
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_buf).strip()

    def handle_data(self, data: str):
        if self._in_title:
            self._title_buf.append(data)


# ---------------------------------------------------------------------------
# Core network helpers
# ---------------------------------------------------------------------------

def _make_request(url: str, method: str = "GET", timeout: int = DEFAULT_TIMEOUT) -> urequest.Request:
    """Build a urllib Request with the standard User-Agent header."""
    req = urequest.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    return req


def _fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str]:
    """
    Fetch *url* and return ``(final_url, html_text)``.

    Raises ``URLError`` / ``HTTPError`` on network or HTTP errors.
    """
    req = _make_request(url, timeout=timeout)
    with urequest.urlopen(req, timeout=timeout) as resp:
        charset = "utf-8"
        ct_header = resp.headers.get("Content-Type", "")
        if "charset=" in ct_header:
            charset = resp.headers.get_param("charset") or "utf-8"
        raw = resp.read()
        return resp.url, raw.decode(charset, errors="replace")


def _parse_metadata(html: str) -> _MetaParser:
    """Parse HTML and return a populated _MetaParser."""
    parser = _MetaParser()
    parser.feed(html)
    return parser


def _domain_from_url(url: str) -> str:
    """Return hostname with 'www.' stripped."""
    host = urlparse(url).hostname or ""
    return host.removeprefix("www.")


def _fetch_title(url: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """
    Fetch *url* and return the page <title>, or None on any error.
    Prints a warning to stderr on failure.
    """
    try:
        _, html = _fetch_html(url, timeout=timeout)
        parser = _parse_metadata(html)
        return parser.title or None
    except (HTTPError, URLError, OSError, ValueError) as exc:
        utils.err(f"fetch failed for {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_fetch_title(args):
    """
    Fetch the <title> of a web page and print it.

    Usage: noteplan-sweep fetch-title <url>

    Exits 0 on success, 1 on any network / HTTP error.
    """
    url = args.url
    timeout = getattr(args, "timeout", DEFAULT_TIMEOUT)
    try:
        _, html = _fetch_html(url, timeout=timeout)
    except HTTPError as exc:
        utils.err(f"{url} — HTTP {exc.code} {exc.reason}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)
    except (URLError, OSError, ValueError) as exc:
        utils.err(f"{url} — {exc}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    parser = _parse_metadata(html)
    if not parser.title:
        utils.err(f"{url} — no <title> found in response")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    utils.log(parser.title)
    sys.exit(utils.EXIT_OK)


def cmd_to_markdown_link(args):
    """
    Fetch the page title for a URL and print it as a Markdown link.

    Usage: noteplan-sweep to-markdown-link <url>

    Prints ``[title](url)``.  If the title cannot be fetched, the domain
    name is used as a fallback.  Always exits 0.
    """
    url = args.url
    timeout = getattr(args, "timeout", DEFAULT_TIMEOUT)
    title = _fetch_title(url, timeout=timeout)
    if not title:
        title = _domain_from_url(url)
    utils.log(f"[{title}]({url})")
    sys.exit(utils.EXIT_OK)


def cmd_fetch_metadata(args):
    """
    Fetch and print YAML metadata for a URL.

    Usage: noteplan-sweep fetch-metadata <url> [--internal-map <json>]

    Fields extracted: title, description, author, published, domain.

    If ``--internal-map`` points to a JSON file mapping ``domain ->
    description``, that mapping is used for the description field and *no*
    network call is made for domains present in the map.

    Prints YAML to stdout.  Exits 0.
    """
    url = args.url
    timeout = getattr(args, "timeout", DEFAULT_TIMEOUT)
    domain = _domain_from_url(url)

    internal_map: dict[str, str] = {}
    if getattr(args, "internal_map", None):
        map_path = Path(args.internal_map)
        try:
            internal_map = json.loads(map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            utils.err(f"could not load internal map {map_path}: {exc}")

    meta: dict[str, str | None] = {
        "title": None,
        "description": internal_map.get(domain),
        "author": None,
        "published": None,
        "domain": domain,
    }

    if domain not in internal_map:
        try:
            _, html = _fetch_html(url, timeout=timeout)
            parser = _parse_metadata(html)
            meta["title"] = parser.title
            if meta["description"] is None:
                meta["description"] = parser.description
            meta["author"] = parser.author
            meta["published"] = parser.published
        except (HTTPError, URLError, OSError, ValueError) as exc:
            utils.err(f"fetch failed for {url}: {exc}")

    # Emit simple YAML (no pyyaml dependency — all values are scalars or None)
    def _yaml_val(v: str | None) -> str:
        if v is None:
            return "null"
        s = str(v)
        # Quote strings containing YAML-significant characters
        if any(c in s for c in ':#{}[]|>&!\'",%@`'):
            escaped = s.replace('"', '\\"')
            return f'"{escaped}"'
        return s

    for key, val in meta.items():
        utils.log(f"{key}: {_yaml_val(val)}")

    sys.exit(utils.EXIT_OK)


def cmd_enrich_urls(args):
    """
    Replace bare URLs in a Markdown file with ``[title](url)`` links.

    Usage: noteplan-sweep enrich-urls <file> [--dry-run-preview]

    URLs already wrapped in a Markdown link are left unchanged.
    URLs whose title cannot be fetched are left as-is (a warning is printed).
    The file is written back via ``utils.write_file`` (respects DRY_RUN).
    """
    path = Path(args.file)
    timeout = getattr(args, "timeout", DEFAULT_TIMEOUT)
    dry_preview = getattr(args, "dry_run_preview", False)

    text = utils.read_file(path)

    # Collect URLs that are already inside a markdown link so we skip them
    already_linked_urls: set[str] = {m.group(1) for m in MD_LINK_RE.finditer(text)}

    # Build a cache: url -> replacement string
    seen: dict[str, str] = {}
    enriched: list[str] = []

    for m in URL_RE.finditer(text):
        url = m.group()
        if url in seen:
            continue
        # Skip if this URL is already a markdown link target
        if url in already_linked_urls:
            seen[url] = url
            continue
        # Also skip if directly preceded by "](" in the raw text
        preceding = text[max(0, m.start() - 2):m.start()]
        if preceding.endswith("]("):
            seen[url] = url
            continue

        title = _fetch_title(url, timeout=timeout)
        if title is None:
            utils.err(f"skipping {url} — could not fetch title")
            seen[url] = url
        else:
            md_link = f"[{title}]({url})"
            seen[url] = md_link
            enriched.append(url)

    if dry_preview:
        for url in enriched:
            utils.log(f"  {url!r} -> {seen[url]!r}")
        utils.log(f"{len(enriched)} URL(s) would be enriched (dry-run preview)")
        sys.exit(utils.EXIT_OK)

    if not enriched:
        utils.log("No bare URLs to enrich.")
        sys.exit(utils.EXIT_OK)

    def _safe_replace(match: re.Match) -> str:
        url = match.group()
        preceding = text[max(0, match.start() - 2):match.start()]
        if preceding.endswith("]("):
            return url
        return seen.get(url, url)

    new_text = URL_RE.sub(_safe_replace, text)
    utils.write_file(path, new_text)
    utils.log(f"Enriched {len(enriched)} URL(s) in {path.name}")
    sys.exit(utils.EXIT_OK)


def cmd_enrich_research_doc(args):
    """
    Fully enrich a research Markdown document.

    Usage: noteplan-sweep enrich-research-doc <file>

    Steps
    -----
    1. Replace bare URLs with ``[title](url)`` markdown links.
    2. Extract all URL domains from the (now-enriched) document.
    3. Merge discovered domains with any existing ``domains:`` frontmatter list.
    4. Update the ``domains:`` frontmatter field.
    5. Write back via ``utils.write_file``.

    Prints a summary of changes.
    """
    path = Path(args.file)
    timeout = getattr(args, "timeout", DEFAULT_TIMEOUT)

    text = utils.read_file(path)

    # ---- Step 1: enrich bare URLs -------------------------------------------
    already_linked_urls: set[str] = {m.group(1) for m in MD_LINK_RE.finditer(text)}
    seen: dict[str, str] = {}

    for m in URL_RE.finditer(text):
        url = m.group()
        if url in seen:
            continue
        if url in already_linked_urls:
            seen[url] = url
            continue
        preceding = text[max(0, m.start() - 2):m.start()]
        if preceding.endswith("]("):
            seen[url] = url
            continue
        title = _fetch_title(url, timeout=timeout)
        if title is None:
            utils.err(f"skipping {url} — could not fetch title")
            seen[url] = url
        else:
            seen[url] = f"[{title}]({url})"

    enriched_count = sum(1 for u, r in seen.items() if r != u)

    def _safe_replace(match: re.Match) -> str:
        url = match.group()
        preceding = text[max(0, match.start() - 2):match.start()]
        if preceding.endswith("]("):
            return url
        return seen.get(url, url)

    enriched_text = URL_RE.sub(_safe_replace, text)

    # ---- Step 2: extract all domains from the enriched document -------------
    all_domains: set[str] = set()
    for m in URL_RE.finditer(enriched_text):
        d = _domain_from_url(m.group())
        if d:
            all_domains.add(d)

    # ---- Steps 3 & 4: read existing frontmatter and update domains: ---------
    existing_domains: list[str] = []

    # YAML frontmatter: text between leading --- delimiters
    fm_match = re.match(r'^---\n(.*?)\n---\n', enriched_text, re.DOTALL)
    if fm_match:
        fm_body = fm_match.group(1)
        # Parse existing domains list (block sequence format)
        dom_block = re.search(
            r'^domains:\s*\n((?:[ \t]+-[^\n]*\n)*)',
            fm_body,
            re.MULTILINE,
        )
        if dom_block:
            existing_domains = re.findall(r'[ \t]+-\s*(.+)', dom_block.group(0))

    merged_domains = sorted(set(existing_domains) | all_domains)
    domains_yaml_block = "domains:\n" + "".join(f"  - {d}\n" for d in merged_domains)

    if fm_match:
        fm_body = fm_match.group(1)
        if re.search(r'^domains:', fm_body, re.MULTILINE):
            # Replace existing domains block (which may span multiple lines)
            new_fm_body = re.sub(
                r'^domains:\s*\n(?:[ \t]+-[^\n]*\n)*',
                domains_yaml_block,
                fm_body,
                flags=re.MULTILINE,
            )
            # If domains was an inline empty list, replace that too
            new_fm_body = re.sub(
                r'^domains:\s*\[\]\s*$',
                domains_yaml_block.rstrip(),
                new_fm_body,
                flags=re.MULTILINE,
            )
        else:
            new_fm_body = fm_body.rstrip() + "\n" + domains_yaml_block.rstrip()
        rest = enriched_text[fm_match.end():]
        final_text = f"---\n{new_fm_body}\n---\n{rest}"
    else:
        # No frontmatter — prepend a minimal one
        final_text = f"---\n{domains_yaml_block}---\n{enriched_text}"

    # ---- Step 5: write back -------------------------------------------------
    utils.write_file(path, final_text)

    new_domain_count = len(set(merged_domains) - set(existing_domains))
    utils.log(
        f"enrich-research-doc: {enriched_count} URL(s) enriched, "
        f"{new_domain_count} new domain(s) added to frontmatter "
        f"({len(merged_domains)} total) in {path.name}"
    )
    sys.exit(utils.EXIT_OK)


def _fetch_with_chrome(url: str, timeout: int = 30) -> tuple[str | None, str | None]:
    """
    Fetch title and description from *url* using the existing Chrome Default
    profile (reuses Okta/SSO cookies already present in the profile).

    Returns ``(title, description)`` — either may be None on failure.

    Requires Playwright: ``pip install playwright && playwright install chromium``
    Chrome must NOT be running when this is called (profile lock conflict).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None, None
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(_CHROME_PROFILE),
                headless=True,
                channel="chrome",
                args=["--no-sandbox"],
            )
            page = ctx.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            title = page.title() or None
            desc_el = page.query_selector(
                'meta[name="description"], meta[property="og:description"]'
            )
            description = desc_el.get_attribute("content") if desc_el else None
            ctx.close()
        return title, description
    except Exception as exc:
        utils.err(f"chrome fetch failed for {url}: {exc}")
        return None, None


def cmd_enrich_links(args):
    """
    Replace bare URLs in a Markdown file with ``[title](url)`` links.

    Usage: noteplan-sweep enrich-links <file> [options]

    Like ``enrich-urls`` but with:
    - Domain skip list: ServiceNow, SharePoint, Okta domains are skipped
      unless ``--use-chrome`` is set.
    - ``--use-chrome``: fetch internal/Okta-protected URLs using the existing
      Chrome Default profile (requires Playwright; Chrome must be closed).
    - ``--interactive``: confirm each replacement interactively (Y/n).
    - ``--dry-run-preview``: print proposed changes without writing.
    """
    path = Path(args.file)
    timeout = getattr(args, "timeout", DEFAULT_TIMEOUT)
    dry_preview = getattr(args, "dry_run_preview", False)
    use_chrome = getattr(args, "use_chrome", False)
    interactive = getattr(args, "interactive", False)

    if use_chrome and not PLAYWRIGHT_AVAILABLE:
        utils.err(
            "--use-chrome requires Playwright.\n"
            "Install with:\n"
            "  pip install playwright\n"
            "  playwright install chromium\n"
            "Then close Chrome before running with --use-chrome."
        )
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    text = utils.read_file(path)

    already_linked_urls: set[str] = {m.group(1) for m in MD_LINK_RE.finditer(text)}

    seen: dict[str, str] = {}
    enriched: list[str] = []

    for m in URL_RE.finditer(text):
        url = m.group()
        if url in seen:
            continue
        if url in already_linked_urls:
            seen[url] = url
            continue
        preceding = text[max(0, m.start() - 2):m.start()]
        if preceding.endswith("]("):
            seen[url] = url
            continue

        # Search engine URLs: auto-format from query param, no network call
        search_label = _search_engine_label(url)
        if search_label:
            md_link = f"[{search_label}]({url})"
            seen[url] = md_link
            enriched.append(url)
            continue

        # Skip binary/image/UUID/session-specific URLs
        if _should_skip_url(url):
            seen[url] = url
            continue

        is_internal = bool(INTERNAL_DOMAINS_RE.match(url))

        if is_internal and not use_chrome:
            utils.err(f"skipping internal URL (use --use-chrome to enrich): {url}")
            seen[url] = url
            continue

        if is_internal:
            title, _ = _fetch_with_chrome(url, timeout=timeout)
        else:
            title = _fetch_title(url, timeout=timeout)

        if title is None:
            utils.err(f"skipping {url} — could not fetch title")
            seen[url] = url
            continue

        md_link = f"[{title}]({url})"

        if interactive:
            sys.stderr.write(f"\n  {url}\n  → {md_link}\n  Enrich? [Y/n] ")
            sys.stderr.flush()
            answer = sys.stdin.readline().strip().lower()
            if answer not in ("", "y", "yes"):
                seen[url] = url
                continue

        seen[url] = md_link
        enriched.append(url)

    if dry_preview:
        for url in enriched:
            utils.log(f"  {url!r}\n    → {seen[url]!r}")
        utils.log(f"\n{len(enriched)} URL(s) would be enriched (dry-run preview)")
        sys.exit(utils.EXIT_OK)

    if not enriched:
        utils.log("No bare URLs to enrich.")
        sys.exit(utils.EXIT_OK)

    def _safe_replace(match: re.Match) -> str:
        url = match.group()
        preceding = text[max(0, match.start() - 2):match.start()]
        if preceding.endswith("]("):
            return url
        return seen.get(url, url)

    new_text = URL_RE.sub(_safe_replace, text)
    utils.write_file(path, new_text)
    utils.log(f"Enriched {len(enriched)} URL(s) in {path.name}")
    sys.exit(utils.EXIT_OK)


def cmd_check_dead_links(args):
    """
    HEAD-check all URLs found in a Markdown file and report dead ones.

    Usage: noteplan-sweep check-dead-links <file> [--timeout N]

    Reports: URL, status code, OK / DEAD.
    Exits 1 if any dead links are found, 0 if all are live.
    """
    path = Path(args.file)
    timeout = getattr(args, "timeout", DEFAULT_TIMEOUT)

    text = utils.read_file(path)
    urls = sorted({m.group() for m in URL_RE.finditer(text)})

    if not urls:
        utils.log("No URLs found.")
        sys.exit(utils.EXIT_OK)

    results: list[tuple[str, str, bool]] = []  # (url, status_label, ok)

    for url in urls:
        req = _make_request(url, method="HEAD", timeout=timeout)
        try:
            with urequest.urlopen(req, timeout=timeout) as resp:
                code = resp.status
                ok = 200 <= code < 400
                results.append((url, str(code), ok))
        except HTTPError as exc:
            ok = exc.code < 400
            results.append((url, str(exc.code), ok))
        except (URLError, OSError, ValueError) as exc:
            results.append((url, str(exc), False))

    dead_count = 0
    for url, status, ok in results:
        label = "OK  " if ok else "DEAD"
        if not ok:
            dead_count += 1
        utils.log(f"  [{label}] {status:<6} {url}")

    utils.log(f"\n{len(urls)} URL(s) checked — {dead_count} dead.")
    sys.exit(utils.EXIT_VALIDATION_FAILURE if dead_count else utils.EXIT_OK)


def cmd_archive_url(args):
    """
    Submit a URL to the Wayback Machine and print the archive link.

    Usage: noteplan-sweep archive-url <url>

    POSTs to ``https://web.archive.org/save/<url>`` and follows the
    redirect to obtain the canonical archive URL.

    Exits 0 on success, 1 on failure.
    """
    url = args.url
    timeout = getattr(args, "timeout", DEFAULT_TIMEOUT)
    save_url = f"https://web.archive.org/save/{url}"

    req = _make_request(save_url, method="POST", timeout=timeout)
    # Wayback Machine requires a Content-Length even for an empty POST body
    req.add_header("Content-Length", "0")

    try:
        with urequest.urlopen(req, timeout=timeout) as resp:
            archive_url = resp.url
    except HTTPError as exc:
        # Wayback may return a 3xx; urllib follows redirects but surfaces
        # HTTPError for 4xx/5xx.  Try to salvage a Location header.
        location = exc.headers.get("Location") if exc.headers else None
        if location:
            archive_url = location
        else:
            utils.err(f"archive failed — HTTP {exc.code}: {exc.reason}")
            sys.exit(utils.EXIT_VALIDATION_FAILURE)
    except (URLError, OSError, ValueError) as exc:
        utils.err(f"archive failed: {exc}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    utils.log(archive_url)
    sys.exit(utils.EXIT_OK)
