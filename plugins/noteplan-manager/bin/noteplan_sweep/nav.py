"""
nav.py — Shared hub navigation bar for all noteplan-sweep HTML dashboards.

Usage:
    from noteplan_sweep.nav import hub_nav_html, ORG_META, ORG_CSS, ORG_JS

    html = f"...{hub_nav_html('insights', tiles)}..."

The nav bar includes:
  - Org switcher (account-style dropdown, persisted in localStorage)
  - Brand "Insights Hub"
  - Nav links: Insights | Plans | Contributions | AI Usage
  - Summary tiles (caller-supplied list of {num, label} dicts)
"""

# ---------------------------------------------------------------------------
# Org definitions
# ---------------------------------------------------------------------------

ORG_META = {
    "all":      {"avatar": "🗂",  "name": "All",        "desc": "Show everything across all orgs"},
    "work":     {"avatar": "🏢",  "name": "ServiceNow", "desc": "Work projects, plans & meetings"},
    "personal": {"avatar": "🏡",  "name": "Personal",   "desc": "Personal projects & goals"},
    "earlbear": {"avatar": "👥",  "name": "EarlBear",   "desc": "EarlBear collaboration"},
}

# ---------------------------------------------------------------------------
# Shared CSS (injected once per page in <style>)
# ---------------------------------------------------------------------------

ORG_CSS = """
  /* ── Hub nav ─────────────────────────────────────────────────────── */
  #hub-nav { background: #010409; border-bottom: 1px solid #21262d; padding: 0 16px; }
  .hub-inner { display: flex; align-items: center; height: 48px; gap: 0; }

  /* Org switcher */
  .org-switcher { position: relative; margin-right: 14px; flex-shrink: 0; }
  .org-btn {
    display: flex; align-items: center; gap: 7px;
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 5px 10px; cursor: pointer; color: #e6edf3;
    font-size: 13px; font-weight: 600; white-space: nowrap;
    transition: border-color 0.15s, background 0.15s;
  }
  .org-btn:hover { background: #21262d; border-color: #58a6ff; }
  .org-avatar { font-size: 16px; line-height: 1; }
  .org-name   { font-size: 13px; }
  .org-caret  { font-size: 10px; color: #6e7681; margin-left: 2px; }
  .org-menu {
    display: none; position: absolute; top: calc(100% + 6px); left: 0;
    background: #161b22; border: 1px solid #30363d; border-radius: 10px;
    min-width: 220px; z-index: 200; overflow: hidden;
    box-shadow: 0 8px 24px rgba(0,0,0,0.6);
  }
  .org-menu.open { display: block; }
  .org-menu-header { font-size: 11px; color: #6e7681; padding: 8px 14px 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  .org-option {
    display: flex; align-items: center; gap: 10px; padding: 8px 14px;
    cursor: pointer; transition: background 0.1s;
  }
  .org-option:hover { background: #21262d; }
  .org-option.active { background: #1f2d4a; }
  .org-opt-avatar { font-size: 20px; width: 28px; text-align: center; flex-shrink: 0; }
  .org-opt-name { font-size: 13px; font-weight: 600; color: #e6edf3; }
  .org-opt-desc { font-size: 11px; color: #6e7681; margin-top: 1px; }
  .org-divider { height: 1px; background: #21262d; margin: 4px 0; }

  /* Brand + links */
  .hub-brand { font-size: 14px; font-weight: 700; color: #8b949e; white-space: nowrap; margin-right: 4px; }
  .hub-links { display: flex; height: 100%; }
  .hub-link {
    display: flex; align-items: center; padding: 0 12px;
    font-size: 13px; color: #6e7681; text-decoration: none;
    border-bottom: 2px solid transparent; white-space: nowrap;
    transition: color 0.12s;
  }
  .hub-link:hover { color: #e6edf3; }
  .hub-link.active { color: #e6edf3; border-bottom-color: #58a6ff; font-weight: 600; cursor: default; }

  /* Summary tiles */
  .hub-tiles { display: flex; gap: 6px; margin-left: auto; }
  .hub-tile {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 4px 14px; text-align: center; min-width: 80px; cursor: default;
    transition: border-color 0.15s;
  }
  .hub-tile:hover { border-color: #58a6ff; }
  .hub-tile-num { font-size: 15px; font-weight: 700; color: #58a6ff; display: block; line-height: 1.4; }
  .hub-tile-lbl { font-size: 9px; color: #6e7681; text-transform: uppercase; letter-spacing: 0.5px; display: block; }

  /* Per-row filter bars */
  .filter-bars { padding: 6px 16px 4px; background: #0d1117; border-bottom: 1px solid #21262d; }
  .fbar { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; padding: 2px 0; }
  .fbar + .fbar { border-top: 1px solid #161b22; padding-top: 4px; margin-top: 2px; }
  .fbar-label { font-size: 10px; color: #484f58; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; width: 52px; flex-shrink: 0; }
"""

# ---------------------------------------------------------------------------
# Shared JS (injected once per page in <script>)
# ---------------------------------------------------------------------------

ORG_JS = """
// ── Org switcher ─────────────────────────────────────────────────────────
const ORG_META = {
  all:      { avatar: '🗂',  name: 'All',        desc: 'Show everything' },
  work:     { avatar: '🏢',  name: 'ServiceNow', desc: 'Work projects & plans' },
  personal: { avatar: '🏡',  name: 'Personal',   desc: 'Personal projects & goals' },
  earlbear: { avatar: '👥',  name: 'EarlBear',   desc: 'EarlBear collaboration' },
};

let activeOrg = localStorage.getItem('noteplan_org') || 'all';

function _applyOrg() {
  const meta = ORG_META[activeOrg] || ORG_META.all;
  const btn = document.getElementById('org-btn');
  if (btn) {
    document.getElementById('org-avatar').textContent = meta.avatar;
    document.getElementById('org-name').textContent   = meta.name;
  }
  document.querySelectorAll('.org-option').forEach(el => {
    el.classList.toggle('active', el.dataset.org === activeOrg);
  });
}

function setOrg(org) {
  activeOrg = org;
  localStorage.setItem('noteplan_org', org);
  _applyOrg();
  document.getElementById('org-menu').classList.remove('open');
  if (typeof rerender === 'function') rerender();
}

function toggleOrgMenu(e) {
  e.stopPropagation();
  document.getElementById('org-menu').classList.toggle('open');
}

document.addEventListener('click', () => {
  const m = document.getElementById('org-menu');
  if (m) m.classList.remove('open');
});

function matchesDomain(domain) {
  return activeOrg === 'all' || !domain || domain === activeOrg;
}
"""

# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def hub_nav_html(
    active_page: str,
    tiles: list[dict] | None = None,
) -> str:
    """
    Return the full hub nav bar HTML string.

    active_page: 'insights' | 'plans' | 'contributions' | 'ai-usage'
    tiles: list of {num: str, label: str, title: str (optional)}
    """
    pages = [
        ("insights",      "/",             "Insights"),
        ("plans",         "/plans",        "Plans"),
        ("contributions", "/contributions","Contributions"),
        ("ai-usage",      "/ai-usage",     "AI Usage"),
    ]

    links_html = ""
    for page_id, href, label in pages:
        if page_id == active_page:
            links_html += f'<span class="hub-link active">{label}</span>'
        else:
            links_html += f'<a class="hub-link" href="{href}" data-page="{page_id}">{label}</a>'

    tiles_html = ""
    for t in (tiles or []):
        tip = f' title="{t["title"]}"' if t.get("title") else ""
        tiles_html += (
            f'<div class="hub-tile"{tip}>'
            f'<span class="hub-tile-num">{t["num"]}</span>'
            f'<span class="hub-tile-lbl">{t["label"]}</span>'
            f'</div>'
        )

    org_options = ""
    for org_id, meta in ORG_META.items():
        org_options += (
            f'<div class="org-option" data-org="{org_id}" onclick="setOrg(\'{org_id}\')">'
            f'<span class="org-opt-avatar">{meta["avatar"]}</span>'
            f'<div><div class="org-opt-name">{meta["name"]}</div>'
            f'<div class="org-opt-desc">{meta["desc"]}</div></div>'
            f'</div>'
        )

    return f"""<div id="hub-nav">
  <div class="hub-inner">
    <div class="org-switcher">
      <button class="org-btn" id="org-btn" onclick="toggleOrgMenu(event)" title="Switch organization">
        <span class="org-avatar" id="org-avatar">🗂</span>
        <span class="org-name"  id="org-name">All</span>
        <span class="org-caret">▾</span>
      </button>
      <div class="org-menu" id="org-menu">
        <div class="org-menu-header">Switch organization</div>
        <div class="org-divider"></div>
        {org_options}
      </div>
    </div>
    <span class="hub-brand">Insights Hub</span>
    <div class="hub-links">{links_html}</div>
    <div class="hub-tiles">{tiles_html}</div>
  </div>
</div>"""
