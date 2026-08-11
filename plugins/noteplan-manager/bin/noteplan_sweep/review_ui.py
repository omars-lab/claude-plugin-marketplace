"""
review_ui.py — Interactive sweep review page (served live by server.py at /review/<id>).

PR-style approve/apply UI: Claude proposes moves (the manifest), the user reviews
a VS Code-like two-column diff per move (source daily note → destination file),
approves/skips/re-routes, and the SERVER executes each approved move with hash
validation. Nothing commits until Finalize.

The page is a plain string with a single substitution (__SESSION_ID__); all data
loads over fetch() from /api/sweep/*, so it always reflects live server state.
Shared theme/helpers come from ui_common (BASE_CSS + JS_HELPERS). The page's pure
logic is exposed on window.__sweepTest for the JS test harness.
"""

import noteplan_sweep.ui_common as ui_common


# ---------------------------------------------------------------------------
# Extra CSS specific to the review UI (single braces — plain string)
# ---------------------------------------------------------------------------

_EXTRA_CSS = """
#offline{display:none;background:#2d0a0a;color:#f85149;padding:6px 16px;font-size:12px;text-align:center}
#offline.on{display:block}
#hdr .prog{font-size:12px;color:#8b949e}
#hdr .meter{display:inline-block;width:120px;height:8px;background:#21262d;border-radius:4px;overflow:hidden;vertical-align:middle;margin:0 6px}
#hdr .meter > i{display:block;height:100%;background:#3fb950}
.legend{display:flex;gap:10px;font-size:11px;align-items:center}
.legend .lg{cursor:pointer;padding:2px 6px;border-radius:4px;border:1px solid transparent;user-select:none}
.legend .lg.dim{opacity:.45}
.lg-sw{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px;vertical-align:middle}
.sw-verbatim{background:#3fb950}.sw-transformed{background:#e3b341}.sw-added{background:#a371f7}
#fin-btn{margin-left:auto;padding:5px 14px;border-radius:5px;border:1px solid #238636;background:#238636;color:#fff;font-size:12px;cursor:pointer}
#fin-btn:disabled{background:#21262d;border-color:#30363d;color:#484f58;cursor:not-allowed}
#queue{width:300px;min-width:200px;background:#161b22;border-right:1px solid #30363d;overflow-y:auto;flex-shrink:0;padding:6px 0}
.q-day{font-size:12px;font-weight:600;color:#58a6ff;padding:8px 12px 4px}
.q-src{font-size:10px;color:#3d6a9e;font-family:monospace;padding:2px 12px 2px 18px}
.q-move{display:flex;align-items:center;gap:8px;padding:5px 12px 5px 24px;cursor:pointer;border-left:3px solid transparent;font-size:12px}
.q-move:hover{background:#21262d}
.q-move.active{background:#21262d;border-left-color:#58a6ff}
.q-move .q-sec{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.q-move .q-dst{color:#484f58;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:90px}
.chip{font-size:12px;width:16px;text-align:center;flex-shrink:0}
.c-pending{color:#8b949e}.c-applying{color:#58a6ff}.c-applied{color:#3fb950}
.c-stale{color:#e3b341}.c-skipped{color:#484f58}.c-failed{color:#f85149}
.c-superseded{color:#30363d}.c-kept{color:#79c0ff}
#queue.f-hide-resolved .q-move.resolved{display:none}
#card{flex:1;overflow-y:auto;padding:16px 20px}
.conf{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px 14px;margin-bottom:12px}
.conf .dots{letter-spacing:2px;margin-right:8px}
.conf .rat{color:#8b949e;font-size:12px}
.conf .alts{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap}
.alt-chip{font-size:11px;padding:2px 8px;border-radius:10px;background:#1c2128;color:#79c0ff;border:1px solid #30363d;cursor:pointer}
.alt-chip:hover{border-color:#58a6ff}
.panes{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pane{border:1px solid #30363d;border-radius:8px;overflow:hidden;min-width:0}
.pane-hdr{background:#161b22;padding:6px 10px;font-size:11px;color:#8b949e;border-bottom:1px solid #30363d;display:flex;justify-content:space-between;gap:8px}
.pane-hdr .fn{color:#e6edf3;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.newbadge{background:#1a1330;color:#c9a7ff;border:1px solid #a371f7;border-radius:3px;padding:0 5px;font-size:10px;font-weight:700}
.code{font-family:'SF Mono','Fira Code',monospace;font-size:11.5px;line-height:18px}
.crow{display:flex;min-height:18px}
.cgut{width:34px;text-align:right;padding:0 6px;color:#484f58;user-select:none;border-right:1px solid #30363d;flex-shrink:0;line-height:18px}
.ctxt{flex:1;padding:0 6px;white-space:pre-wrap;word-break:break-word;line-height:18px}
.crow.ctx{background:#0d1117}
.crow.out{background:#20110f}.crow.out .cgut{color:#f0883e}.crow.out .ctxt{color:#ffb4a3}
.crow.out.sel{background:#3a1d10;outline:1px solid #f0883e}
.crow.out.mismatch .ctxt{text-decoration:underline wavy #e3b341}
.crow.prov-verbatim{background:#0e4429}.crow.prov-verbatim .cgut{color:#3fb950}.crow.prov-verbatim .ctxt{color:#aff5b4}
.crow.prov-transformed{background:#1f1200}.crow.prov-transformed .cgut{color:#e3b341}.crow.prov-transformed .ctxt{color:#f0d78c}
.crow.prov-added{background:#1a1330}.crow.prov-added .cgut{color:#c9a7ff}.crow.prov-added .ctxt{color:#d7bcff;font-style:italic}
.crow.orig{opacity:.55;background:#160d00}.crow.orig .ctxt{text-decoration:line-through;color:#b08a3a}
.ins-rule{font-size:10px;color:#58a6ff;padding:3px 8px;background:#0d1117;border-top:1px solid #21262d;border-bottom:1px solid #21262d}
.sel-dim .crow.prov-verbatim,.sel-dim .crow.prov-added{opacity:.35}
#pill{position:fixed;display:none;z-index:500;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:6px;gap:6px;box-shadow:0 4px 16px rgba(0,0,0,.5)}
#pill.on{display:flex}
#pill button{font-size:11px;padding:3px 8px;border-radius:4px;border:1px solid #30363d;background:#21262d;color:#e6edf3;cursor:pointer}
#pill button:hover{border-color:#58a6ff}
#actionbar{margin-top:14px;display:flex;gap:8px;align-items:center}
#actionbar button{font-size:12px;padding:6px 14px;border-radius:5px;border:1px solid #30363d;background:#21262d;color:#e6edf3;cursor:pointer}
#actionbar button.primary{background:#238636;border-color:#238636;color:#fff}
#actionbar button:disabled{opacity:.4;cursor:not-allowed}
.banner{padding:8px 12px;border-radius:6px;font-size:12px;margin-bottom:10px}
.banner.stale{background:#2d1f00;color:#e3b341;border:1px solid #6b4e00}
.banner.info{background:#0d1b2a;color:#79c0ff;border:1px solid #1f4a6b}
#picker,#finalize-screen{position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:1000;display:none;align-items:center;justify-content:center}
#picker.on,#finalize-screen.on{display:flex}
.pmodal{background:#161b22;border:1px solid #30363d;border-radius:10px;width:min(680px,92vw);max-height:80vh;overflow:auto;padding:16px}
.pmodal h3{font-size:14px;margin-bottom:10px;color:#e6edf3}
.pmodal input{width:100%;padding:6px 10px;background:#0d1117;border:1px solid #30363d;border-radius:5px;color:#e6edf3;font-size:12px;margin-bottom:8px}
.plist{max-height:260px;overflow:auto}
.pitem{padding:5px 8px;border-radius:4px;cursor:pointer;font-size:12px}
.pitem:hover,.pitem.sel{background:#21262d}
.pitem .sub{color:#484f58;font-size:10px;font-family:monospace}
.fin-summary{max-width:760px;width:92vw;background:#0d1117}
.fin-summary textarea{width:100%;min-height:110px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:8px;font-family:monospace;font-size:12px}
.tally{font-size:12px;color:#8b949e;margin:8px 0}
.kbd{font-family:monospace;background:#21262d;border:1px solid #30363d;border-radius:3px;padding:0 4px;font-size:10px}
.empty-state{color:#484f58;text-align:center;padding:60px 20px}
"""


# ---------------------------------------------------------------------------
# Body HTML
# ---------------------------------------------------------------------------

_BODY = """
<div id="offline">⚠ Server unreachable — changes paused. Retrying…</div>
<div id="hdr">
  <h1>Sweep Review — __SESSION_ID__</h1>
  <span class="prog" id="prog"></span>
  <span class="meter"><i id="meter-fill" style="width:0%"></i></span>
  <div class="legend">
    <span class="lg" data-prov="verbatim" title="moved as-is"><span class="lg-sw sw-verbatim"></span>verbatim</span>
    <span class="lg" data-prov="transformed" title="reworded / re-tagged"><span class="lg-sw sw-transformed"></span>reworded</span>
    <span class="lg" data-prov="added" title="added by agent"><span class="lg-sw sw-added"></span>agent-added</span>
  </div>
  <button id="fin-btn" disabled onclick="openFinalize()">Finalize ▸</button>
</div>
<div id="layout">
  <nav id="queue"></nav>
  <main id="card"><div class="empty-state">Loading…</div></main>
</div>
<div id="pill">
  <button onclick="pillReroute()">⇢ Re-route <span class="kbd">r</span></button>
  <button onclick="pillKeep()">↩ Keep in source <span class="kbd">k</span></button>
  <button onclick="clearSelection()">✕</button>
</div>
<div id="picker"><div class="pmodal">
  <h3>Re-route to…</h3>
  <input id="picker-q" placeholder="Search notes by name…" oninput="pickerSearch()">
  <div class="plist" id="picker-list"></div>
</div></div>
<div id="finalize-screen"><div class="pmodal fin-summary">
  <h3>Finalize sweep</h3>
  <div id="fin-body"></div>
</div></div>
"""


# ---------------------------------------------------------------------------
# Page JS (raw string — single braces OK)
# ---------------------------------------------------------------------------

_PAGE_JS = r"""
const RUN_ID = "__SESSION_ID__";

// ── Pure logic (exposed on window.__sweepTest) ──────────────────────────────

// Selection over a move's source-line indices.
function selectionReduce(sel, action) {
  const a = action || {};
  const set = new Set(sel.selected || []);
  switch (a.type) {
    case 'click':      return { anchor: a.idx, selected: [a.idx] };
    case 'toggle': {
      if (set.has(a.idx)) set.delete(a.idx); else set.add(a.idx);
      return { anchor: a.idx, selected: [...set].sort((x, y) => x - y) };
    }
    case 'shiftClick': {
      const anchor = (sel.anchor == null) ? a.idx : sel.anchor;
      const lo = Math.min(anchor, a.idx), hi = Math.max(anchor, a.idx);
      const range = []; for (let i = lo; i <= hi; i++) range.push(i);
      return { anchor, selected: range };
    }
    case 'clear':      return { anchor: null, selected: [] };
    default:           return sel;
  }
}

// Provenance → css class.
function classifyProvenance(prov) {
  return prov === 'transformed' ? 'prov-transformed'
       : prov === 'added'       ? 'prov-added'
       : 'prov-verbatim';
}

// Status → {glyph, cls, label, resolved}.
function statusMeta(status) {
  const M = {
    pending:    { glyph: '●', cls: 'c-pending',    label: 'pending',   resolved: false },
    applying:   { glyph: '◌', cls: 'c-applying',   label: 'applying…', resolved: false },
    applied:    { glyph: '✓', cls: 'c-applied',    label: 'applied',   resolved: true  },
    skipped:    { glyph: '–', cls: 'c-skipped',    label: 'skipped',   resolved: true  },
    kept:       { glyph: '↩', cls: 'c-kept',       label: 'kept',      resolved: true  },
    stale:      { glyph: '⚠', cls: 'c-stale',      label: 'stale',     resolved: false },
    failed:     { glyph: '✗', cls: 'c-failed',     label: 'failed',    resolved: false },
    superseded: { glyph: '⋯', cls: 'c-superseded', label: 'superseded',resolved: true  },
  };
  return M[status] || M.pending;
}

function canFinalize(counts) {
  if (!counts) return false;
  return (counts.unresolved === 0) && (counts.total > 0);
}

// Word-level diff for transformed lines: prefix/suffix trim, middle marked.
function wordDiff(orig, next) {
  const a = String(orig).split(/(\s+)/), b = String(next).split(/(\s+)/);
  let p = 0; while (p < a.length && p < b.length && a[p] === b[p]) p++;
  let sa = a.length - 1, sb = b.length - 1;
  while (sa >= p && sb >= p && a[sa] === b[sb]) { sa--; sb--; }
  const out = [];
  for (let i = 0; i < p; i++) out.push({ t: a[i], op: 'same' });
  for (let i = p; i <= sa; i++) out.push({ t: a[i], op: 'del' });
  for (let i = p; i <= sb; i++) out.push({ t: b[i], op: 'add' });
  for (let i = sa + 1; i < a.length; i++) out.push({ t: a[i], op: 'same' });
  return out;
}

// Client-side split (mirrors sweep_manifest.split_move) for optimistic preview.
function splitMoveClient(move, parts) {
  const src = move.source.lines, n = src.length;
  const seen = new Set();
  for (const p of parts) for (const i of (p.line_idxs || [])) {
    if (i < 0 || i >= n) throw new Error('index out of range: ' + i);
    if (seen.has(i)) throw new Error('index in multiple parts: ' + i);
    seen.add(i);
  }
  const children = []; let k = 0;
  for (const p of parts) {
    const idxs = [...(p.line_idxs || [])].sort((x, y) => x - y);
    if (!idxs.length || p.keep_in_source) continue;
    const chosen = idxs.map(i => src[i]);
    const chosenNs = new Set(chosen.map(l => l.n));
    const child = JSON.parse(JSON.stringify(move));
    child.id = move.id + '-' + String.fromCharCode(97 + k);
    child.source.lines = chosen;
    child.source.line_start = chosen[0].n;
    child.source.line_end = chosen[chosen.length - 1].n;
    child.content.lines = move.content.lines.filter(cl => chosenNs.has(cl.source_n));
    if (p.dest) Object.assign(child.destination, p.dest);
    children.push(child); k++;
  }
  return children;
}

window.__sweepTest = { selectionReduce, classifyProvenance, statusMeta,
                       canFinalize, wordDiff, splitMoveClient };

// ── Store + API ─────────────────────────────────────────────────────────────

const store = { manifest: null, state: null, currentId: null,
                selection: { anchor: null, selected: [] },
                destCache: {}, provFilter: null };

async function api(method, path, body) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(path, opts);
    document.getElementById('offline').classList.remove('on');
    return { code: r.status, data: await r.json() };
  } catch (e) {
    document.getElementById('offline').classList.add('on');
    throw e;
  }
}

async function load() {
  const { data } = await api('GET', `/api/sweep/session/${RUN_ID}`);
  store.manifest = data.manifest;
  store.state = data.state;
  if (!store.currentId) {
    const first = store.state.moves.find(m => statusMeta(m.status).resolved === false);
    store.currentId = first ? first.id : (store.state.moves[0] || {}).id;
  }
  render();
}

function applyState(data) {
  if (data && data.state) { store.state = data.state; render(); }
}

// ── Rendering ────────────────────────────────────────────────────────────────

function visibleMoves() {
  return (store.state.moves || []).filter(m => m.status !== 'superseded');
}
function currentMove() {
  return (store.state.moves || []).find(m => m.id === store.currentId);
}

function render() {
  renderHeader();
  renderQueue();
  renderCard();
}

function renderHeader() {
  const c = store.state.counts;
  document.getElementById('prog').textContent =
    `${c.resolved}/${c.total} resolved · ${c.applied} applied · ${c.stale} stale`;
  const pct = c.total ? Math.round((c.resolved / c.total) * 100) : 0;
  document.getElementById('meter-fill').style.width = pct + '%';
  const fin = document.getElementById('fin-btn');
  fin.disabled = !(store.state.state === 'open' && canFinalize(c));
  if (store.state.state === 'finalized') {
    fin.textContent = '✓ ' + (store.state.commit_sha || 'finalized');
    fin.disabled = true;
  }
}

function renderQueue() {
  const q = document.getElementById('queue');
  q.innerHTML = '';
  let lastDay = null, lastSrc = null;
  for (const m of visibleMoves()) {
    const day = m.source.file.replace(/^Calendar\//, '').replace(/\.md$/, '');
    if (day !== lastDay) {
      const d = document.createElement('div'); d.className = 'q-day';
      d.textContent = '📅 ' + day; q.appendChild(d); lastDay = day; lastSrc = null;
    }
    if (m.source.file !== lastSrc) {
      const s = document.createElement('div'); s.className = 'q-src';
      s.textContent = m.source.file; q.appendChild(s); lastSrc = m.source.file;
    }
    const meta = statusMeta(m.status);
    const el = document.createElement('div');
    el.className = 'q-move' + (m.id === store.currentId ? ' active' : '')
                 + (meta.resolved ? ' resolved' : '');
    const dst = m.destination.file.split('/').pop().replace(/\.md$/, '');
    const glyph = (m.rerouted && m.status === 'pending') ? '⇢' : meta.glyph;
    el.innerHTML = `<span class="chip ${meta.cls}">${glyph}</span>`
      + `<span class="q-sec">${esc(m.source.section_header.replace(/^#+\s*/, ''))}</span>`
      + `<span class="q-dst">${esc(dst)}</span>`;
    el.onclick = () => { store.currentId = m.id; clearSelection(); render(); };
    q.appendChild(el);
  }
}

function confDots(level) {
  const n = level === 'high' ? 3 : level === 'medium' ? 2 : 1;
  const color = level === 'high' ? '#3fb950' : level === 'medium' ? '#e3b341' : '#f85149';
  return `<span class="dots" style="color:${color}">${'●'.repeat(n)}${'○'.repeat(3 - n)}</span>`;
}

async function renderCard() {
  const card = document.getElementById('card');
  const m = currentMove();
  if (!m) { card.innerHTML = '<div class="empty-state">No moves in this session.</div>'; return; }

  const cls = m.classification || {};
  let html = '';

  if (store.state.state === 'finalized') {
    html += `<div class="banner info">Session finalized as <b>${esc(store.state.commit_sha || '')}</b> — read-only.</div>`;
  }
  if (m.status === 'stale' || m.status === 'failed') {
    html += `<div class="banner stale">⚠ This move is <b>${m.status}</b> — the source changed since it was proposed. Rebase (<span class="kbd">⇧R</span>), skip, or re-route.</div>`;
  }

  // Confidence card
  html += `<div class="conf">${confDots(cls.confidence || 'high')}`
    + `<span class="rat">${esc(cls.rationale || '')}</span>`;
  if ((cls.alternatives || []).length) {
    html += '<div class="alts">';
    cls.alternatives.forEach((alt, i) => {
      html += `<span class="alt-chip" onclick="rerouteTo(${i})" title="${esc(alt.reason || '')}">`
        + `→ ${esc(alt.file.split('/').pop().replace(/\.md$/, ''))}</span>`;
    });
    html += '</div>';
  }
  html += '</div>';

  // Panes
  html += '<div class="panes">'
    + `<div class="pane" id="src-pane"><div class="pane-hdr"><span>SOURCE</span>`
    + `<span class="fn">${esc(m.source.file)}</span></div><div class="code" id="src-code"></div></div>`
    + `<div class="pane" id="dst-pane"><div class="pane-hdr"><span>DEST`
    + (m.destination.exists ? '' : ' <span class="newbadge">NEW FILE</span>')
    + `</span><span class="fn">${esc(m.destination.file.split('/').pop())}</span></div>`
    + `<div class="code" id="dst-code"></div></div></div>`;

  // Action bar
  const ro = store.state.state !== 'open';
  const applied = m.status === 'applied' || m.status === 'skipped' || m.status === 'kept';
  html += '<div id="actionbar">'
    + `<button class="primary" onclick="approve()" ${ro || applied ? 'disabled' : ''}>Approve &amp; apply <span class="kbd">a</span></button>`
    + `<button onclick="decide('skip')" ${ro ? 'disabled' : ''}>Skip <span class="kbd">s</span></button>`
    + `<button onclick="rerouteWhole()" ${ro ? 'disabled' : ''}>Re-route <span class="kbd">r</span></button>`
    + ((m.status === 'stale' || m.status === 'failed')
        ? `<button onclick="rebase()">Rebase <span class="kbd">⇧R</span></button>` : '')
    + `<button onclick="openInNotePlan()">Open in NotePlan <span class="kbd">o</span></button>`
    + '</div>';

  card.innerHTML = html;

  await renderSource(m);
  await renderDest(m);
}

async function fetchFile(path, start, end) {
  const key = `${path}:${start || ''}:${end || ''}`;
  if (store.destCache[key]) return store.destCache[key];
  let url = `/api/sweep/file?path=${encodeURIComponent(path)}`;
  if (start) url += `&start=${start}&end=${end}`;
  const { data } = await api('GET', url);
  store.destCache[key] = data;
  return data;
}

async function renderSource(m) {
  const el = document.getElementById('src-code');
  if (!el) return;
  const outTexts = m.source.lines.map(l => l.text);
  const k = outTexts.length;
  // Fetch the whole source (daily notes are small) so we can content-anchor the
  // outgoing run even after earlier approved moves shifted line numbers — the
  // manifest's line_start is only a hint, never trusted for display.
  const file = await fetchFile(m.source.file);
  const lines = file.lines || [];
  // Locate the contiguous run matching outTexts; prefer the one nearest the hint.
  const hint = (m.source.line_start || 1) - 1;
  let pos = -1, best = 1e9;
  for (let i = 0; i + k <= lines.length; i++) {
    let ok = true;
    for (let j = 0; j < k; j++) if (lines[i + j] !== outTexts[j]) { ok = false; break; }
    if (ok && Math.abs(i - hint) < best) { best = Math.abs(i - hint); pos = i; }
  }
  let html = '';
  if (pos < 0) {
    // Stale — the exact run isn't on disk; show the hint window as context.
    const from = Math.max(0, hint - 3), to = Math.min(lines.length, hint + k + 3);
    for (let i = from; i < to; i++)
      html += `<div class="crow ctx"><span class="cgut">${i + 1}</span><span class="ctxt">${esc(lines[i]) || ' '}</span></div>`;
    html += '<div class="crow ctx"><span class="cgut">⚠</span><span class="ctxt">(outgoing lines not found at this position — move is stale)</span></div>';
    el.innerHTML = html;
    return;
  }
  const from = Math.max(0, pos - 3), to = Math.min(lines.length, pos + k + 3);
  for (let i = from; i < to; i++) {
    const no = i + 1;
    const isOut = i >= pos && i < pos + k;
    const idx = isOut ? i - pos : -1;
    const selCls = (isOut && store.selection.selected.includes(idx)) ? ' sel' : '';
    html += `<div class="crow ${isOut ? 'out' : 'ctx'}${selCls}" data-idx="${isOut ? idx : ''}">`
      + `<span class="cgut">${no}</span><span class="ctxt">${esc(lines[i]) || ' '}</span></div>`;
  }
  el.innerHTML = html;
  el.querySelectorAll('.crow.out').forEach(row => {
    row.onclick = (e) => {
      const idx = parseInt(row.dataset.idx, 10);
      const type = e.shiftKey ? 'shiftClick' : (e.metaKey || e.ctrlKey) ? 'toggle' : 'click';
      store.selection = selectionReduce(store.selection, { type, idx });
      renderSource(m); positionPill(e);
    };
  });
}

async function renderDest(m) {
  const el = document.getElementById('dst-code');
  if (!el) return;
  const content = m.content.lines;
  const section = m.destination.section_header;

  if (!m.destination.exists) {
    // New-file preview: create block rendered as agent-added
    let html = '';
    const create = m.destination.create || {};
    const pre = [];
    if (create.frontmatter) { pre.push('---'); for (const k in create.frontmatter) pre.push(`${k}: ${create.frontmatter[k]}`); pre.push('---'); }
    if (create.h1) pre.push(create.h1);
    (create.boilerplate_lines || []).forEach(b => pre.push(b));
    pre.forEach((l, i) => { html += provRow(i + 1, l, 'prov-added'); });
    html += `<div class="ins-rule">── inserted under "${esc(section)}" ──</div>`;
    html += contentRows(content, pre.length + 1);
    el.innerHTML = html;
    return;
  }

  const file = await fetchFile(m.destination.file);
  const lines = file.lines || [];
  // Find the section header; insert content right after its existing body.
  let hdr = -1;
  for (let i = 0; i < lines.length; i++) if (lines[i].trim() === section.trim()) hdr = i;
  let insertAt = lines.length;
  if (hdr >= 0) {
    insertAt = lines.length;
    for (let i = hdr + 1; i < lines.length; i++) if (/^# /.test(lines[i])) { insertAt = i; break; }
    while (insertAt > hdr + 1 && lines[insertAt - 1].trim() === '') insertAt--;
  }
  let html = '';
  const CTX = 4;  // context lines around the insertion — a focused PR-style hunk
  const show = (from, to) => { for (let i = from; i < to; i++) html += `<div class="crow ctx"><span class="cgut">${i + 1}</span><span class="ctxt">${esc(lines[i]) || ' '}</span></div>`; };
  const gap = (n) => { if (n > 0) html += `<div class="ins-rule" style="color:#484f58">⋯ ${n} line${n === 1 ? '' : 's'} above ⋯</div>`; };
  if (hdr < 0) {
    // Section absent → created at EOF. Show a tail of the file as context.
    const from = Math.max(0, lines.length - CTX);
    gap(from);
    show(from, lines.length);
    html += `<div class="ins-rule">section "${esc(section)}" will be created at end of file</div>`;
    html += contentRows(content, lines.length + 1);
  } else {
    // Focused hunk: section header … CTX lines before insertion … inserted … CTX after.
    const winStart = Math.max(hdr, insertAt - CTX);
    gap(winStart);
    if (winStart > hdr) { show(hdr, hdr + 1); if (winStart > hdr + 1) html += `<div class="ins-rule" style="color:#484f58">⋯</div>`; }
    show(winStart, insertAt);
    html += `<div class="ins-rule">── inserted under "${esc(section)}" ──</div>`;
    html += contentRows(content, insertAt + 1);
    const after = Math.min(lines.length, insertAt + CTX);
    show(insertAt, after);
    if (after < lines.length) html += `<div class="ins-rule" style="color:#484f58">⋯ ${lines.length - after} more ⋯</div>`;
  }
  el.innerHTML = html;
}

function provRow(no, text, cls, orig) {
  const gl = cls === 'prov-verbatim' ? '＝' : cls === 'prov-transformed' ? '✎' : '⚙';
  let inner = esc(text) || ' ';
  if (cls === 'prov-transformed' && orig != null) {
    inner = wordDiff(orig, text).map(w =>
      w.op === 'add' ? `<b style="color:#7ee787">${esc(w.t)}</b>` :
      w.op === 'del' ? '' : esc(w.t)).join('');
    inner += ` <span title="${esc(orig)}" style="opacity:.5">✎</span>`;
  }
  return `<div class="crow ${cls}"><span class="cgut">${gl}</span><span class="ctxt">${inner}</span></div>`
    + ((cls === 'prov-transformed' && orig != null)
        ? `<div class="crow orig"><span class="cgut"></span><span class="ctxt">${esc(orig)}</span></div>` : '');
}

function contentRows(content, startNo) {
  let html = '', no = startNo;
  for (const cl of content) {
    const cls = classifyProvenance(cl.provenance);
    html += provRow(no, cl.text, cls, cl.provenance === 'transformed' ? cl.original : null);
    no++;
  }
  return html;
}

// ── Selection pill ──────────────────────────────────────────────────────────

function positionPill(e) {
  const pill = document.getElementById('pill');
  if (!store.selection.selected.length) { pill.classList.remove('on'); return; }
  pill.classList.add('on');
  pill.style.left = Math.min(e.clientX, window.innerWidth - 260) + 'px';
  pill.style.top = (e.clientY + 14) + 'px';
}
function clearSelection() {
  store.selection = selectionReduce(store.selection, { type: 'clear' });
  document.getElementById('pill').classList.remove('on');
  const m = currentMove(); if (m) renderSource(m);
}

// ── Actions ──────────────────────────────────────────────────────────────────

async function approve() {
  const m = currentMove(); if (!m) return;
  const { code, data } = await api('POST', `/api/sweep/session/${RUN_ID}/approve`,
    { move_ids: [m.id], expect_seq: store.state.seq });
  applyState(data);
  if (code === 200) advance();
}

async function decide(action, payload) {
  const m = currentMove(); if (!m) return;
  const { data } = await api('POST', `/api/sweep/session/${RUN_ID}/decision`,
    { move_id: m.id, action, payload: payload || {}, expect_seq: store.state.seq });
  applyState(data);
  if (action === 'skip') advance();
}

async function rebase() {
  const m = currentMove(); if (!m) return;
  const { data } = await api('POST', `/api/sweep/session/${RUN_ID}/decision`,
    { move_id: m.id, action: 'refresh', expect_seq: store.state.seq });
  applyState(data);
}

function advance() {
  const vis = visibleMoves();
  const idx = vis.findIndex(m => m.id === store.currentId);
  const next = vis.slice(idx + 1).find(m => !statusMeta(m.status).resolved);
  if (next) { store.currentId = next.id; clearSelection(); render(); }
}

function move(delta) {
  const vis = visibleMoves();
  const idx = vis.findIndex(m => m.id === store.currentId);
  const ni = Math.max(0, Math.min(vis.length - 1, idx + delta));
  if (vis[ni]) { store.currentId = vis[ni].id; clearSelection(); render(); }
}

function openInNotePlan() {
  const m = currentMove(); if (!m) return;
  window.location.href = xcallbackUrl(m.destination.file.split('/').pop());
}

// ── Re-route + split ──────────────────────────────────────────────────────────

let pickerMode = null;  // 'whole' | 'selection'
function rerouteWhole() { pickerMode = 'whole'; openPicker(); }
function pillReroute() { pickerMode = 'selection'; openPicker(); }
function pillKeep() {
  // Keep selected lines in source: split them out as keep_in_source.
  const m = currentMove(); const sel = store.selection.selected;
  if (!m || !sel.length) return;
  const all = m.source.lines.map((_, i) => i);
  const rest = all.filter(i => !sel.includes(i));
  const parts = [{ line_idxs: sel, keep_in_source: true }];
  if (rest.length) parts.push({ line_idxs: rest });
  doSplit(parts);
}
async function rerouteTo(altIdx) {
  const m = currentMove(); const alt = (m.classification.alternatives || [])[altIdx];
  if (!alt) return;
  const { data } = await api('POST', `/api/sweep/session/${RUN_ID}/decision`,
    { move_id: m.id, action: 'reroute',
      payload: { dest: { file: alt.file, section_header: alt.section_header } },
      expect_seq: store.state.seq });
  applyState(data);
}

function openPicker() {
  document.getElementById('picker').classList.add('on');
  document.getElementById('picker-q').value = '';
  document.getElementById('picker-q').focus();
  pickerSearch();
}
function closePicker() { document.getElementById('picker').classList.remove('on'); }

async function pickerSearch() {
  const q = document.getElementById('picker-q').value;
  const m = currentMove();
  const { data } = await api('GET', `/api/sweep/files?q=${encodeURIComponent(q)}`);
  const list = document.getElementById('picker-list');
  const alts = (m.classification.alternatives || []).map(a =>
    ({ stem: a.file.split('/').pop().replace(/\.md$/, ''), path: a.file,
       section: a.section_header, alt: true }));
  const files = alts.concat(data.files || []);
  list.innerHTML = files.map((f, i) =>
    `<div class="pitem" onclick="pickDest('${esc(f.path)}','${esc(f.section || '')}')">`
    + `${f.alt ? '★ ' : ''}${esc(f.stem)}<div class="sub">${esc(f.path)}</div></div>`).join('');
}

async function pickDest(path, section) {
  closePicker();
  const m = currentMove();
  const dest = { file: path, section_header: section || '# Notes' };
  if (pickerMode === 'whole') {
    const { data } = await api('POST', `/api/sweep/session/${RUN_ID}/decision`,
      { move_id: m.id, action: 'reroute', payload: { dest }, expect_seq: store.state.seq });
    applyState(data);
  } else {
    const sel = store.selection.selected;
    const all = m.source.lines.map((_, i) => i);
    const rest = all.filter(i => !sel.includes(i));
    const parts = [{ line_idxs: sel, dest }];
    if (rest.length) parts.push({ line_idxs: rest });
    doSplit(parts);
  }
}

async function doSplit(parts) {
  const m = currentMove();
  const { data } = await api('POST', `/api/sweep/session/${RUN_ID}/split`,
    { move_id: m.id, parts, expect_seq: store.state.seq });
  clearSelection();
  applyState(data);
}

// ── Finalize ──────────────────────────────────────────────────────────────────

async function openFinalize() {
  const { data } = await api('GET', `/api/sweep/session/${RUN_ID}/summary`);
  const t = data.provenance || {};
  const body = document.getElementById('fin-body');
  body.innerHTML =
    `<div class="tally">Applied moves: <b>${data.counts.applied}</b> · `
    + `skipped ${data.counts.skipped} · kept ${data.counts.kept} · `
    + `＝${t.verbatim} ✎${t.transformed} ⚙${t.added}</div>`
    + `<div class="tally">Files: ${(data.files || []).map(f => esc(f)).join(', ')}</div>`
    + `<textarea id="fin-msg">${esc(data.commit_message || '')}</textarea>`
    + `<div id="actionbar"><button class="primary" onclick="doFinalize()">Commit &amp; finalize</button>`
    + `<button onclick="closeFinalize()">Cancel</button>`
    + `<button onclick="doAbort()" style="margin-left:auto;color:#f85149">Abort session</button></div>`
    + `<div id="fin-result"></div>`;
  document.getElementById('finalize-screen').classList.add('on');
}
function closeFinalize() { document.getElementById('finalize-screen').classList.remove('on'); }

async function doFinalize() {
  const msg = document.getElementById('fin-msg').value;
  const { code, data } = await api('POST', `/api/sweep/session/${RUN_ID}/finalize`,
    { commit_message: msg, expect_seq: store.state.seq });
  if (code === 200) {
    applyState(data);
    document.getElementById('fin-result').innerHTML =
      `<div class="banner info">✓ Finalized as <b>${esc(data.commit_sha)}</b></div>`;
    setTimeout(() => { closeFinalize(); render(); }, 1200);
  } else {
    const errs = (data.report && data.report.errors) || [data.error || 'failed'];
    applyState(data);
    document.getElementById('fin-result').innerHTML =
      `<div class="banner stale">Validation failed:<br>${errs.map(esc).join('<br>')}</div>`;
  }
}

async function doAbort() {
  if (!confirm('Abort session? All applied moves will be reverted (nothing was committed).')) return;
  const { data } = await api('POST', `/api/sweep/session/${RUN_ID}/abort`,
    { expect_seq: store.state.seq });
  applyState(data); closeFinalize();
}

// ── Keyboard ──────────────────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
    if (e.key === 'Escape') { closePicker(); closeFinalize(); }
    return;
  }
  if (e.key === 'Escape') { clearSelection(); closePicker(); closeFinalize(); return; }
  if (e.key === 'j') move(1);
  else if (e.key === 'k') { store.selection.selected.length ? pillKeep() : move(-1); }
  else if (e.key === 'a') approve();
  else if (e.key === 's') decide('skip');
  else if (e.key === 'r') { store.selection.selected.length ? pillReroute() : rerouteWhole(); }
  else if (e.key === 'R' && e.shiftKey) rebase();
  else if (e.key === 'o') openInNotePlan();
  else if (e.key === 'f') { if (!document.getElementById('fin-btn').disabled) openFinalize(); }
});

// Provenance legend filters
document.querySelectorAll('.legend .lg').forEach(lg => {
  lg.onclick = () => {
    const prov = lg.dataset.prov;
    store.provFilter = store.provFilter === prov ? null : prov;
    document.querySelectorAll('.legend .lg').forEach(x =>
      x.classList.toggle('dim', store.provFilter && x.dataset.prov !== store.provFilter));
    const card = document.getElementById('card');
    card.classList.toggle('sel-dim', store.provFilter === 'transformed');
  };
});

// Poll for out-of-band changes every 10s.
setInterval(async () => {
  if (store.state && store.state.state !== 'open') return;
  try {
    const { data } = await api('GET', `/api/sweep/session/${RUN_ID}/status`);
    if (data && data.seq !== store.state.seq) load();
  } catch (e) { /* offline banner handled in api() */ }
}, 10000);

load();
"""


# ---------------------------------------------------------------------------
# Compose the full page
# ---------------------------------------------------------------------------

HTML_TEMPLATE = (
    "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<title>Sweep Review — __SESSION_ID__</title>\n"
    "<style>\n" + ui_common.BASE_CSS + "\n" + _EXTRA_CSS + "\n</style>\n"
    "</head>\n<body>\n"
    + _BODY +
    "\n<script>\n" + ui_common.JS_HELPERS + "\n" + _PAGE_JS + "\n</script>\n"
    "</body>\n</html>\n"
)


def build_review_ui_html(run_id: str) -> str:
    return HTML_TEMPLATE.replace("__SESSION_ID__", run_id)
