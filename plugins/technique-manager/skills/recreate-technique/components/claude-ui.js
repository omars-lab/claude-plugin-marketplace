/*
 * claude-ui.js: the one component library every technique page, the gallery and the
 * catalog render with. React 18 + htm tagged templates, so there is no build step.
 *
 * Loaded after vendor/react, vendor/react-dom and vendor/htm. Exposes window.ClaudeUI.
 *
 * Rule: a page never carries its own markup. A spec is a list of blocks, and each block
 * type maps to exactly one component in BLOCKS below. A UI element no component covers
 * yet gets a new component here (and a sample in SAMPLES), never a one-off in a page.
 */
(function () {
  "use strict";
  var React = window.React;
  var html = window.htm.bind(React.createElement);

  // ── Inline text: **bold**, *italic*, `code`, and nothing else. Text stays text (no innerHTML). ──
  function Inline(props) {
    var text = String(props.text == null ? "" : props.text);
    var parts = [];
    var re = /(\*\*[^*]+\*\*|`[^`]+`|(?<![\w*])\*[^*\s][^*]*?\*(?![\w*]))/g;
    var last = 0, m, i = 0;
    while ((m = re.exec(text))) {
      if (m.index > last) parts.push(text.slice(last, m.index));
      var tok = m[0];
      if (tok.slice(0, 2) === "**") parts.push(html`<strong key=${i++}>${tok.slice(2, -2)}</strong>`);
      else if (tok[0] === "*") parts.push(html`<em key=${i++}>${tok.slice(1, -1)}</em>`);
      else parts.push(html`<span class="cu-code" key=${i++}>${tok.slice(1, -1)}</span>`);
      last = m.index + tok.length;
    }
    if (last < text.length) parts.push(text.slice(last));
    return html`<${React.Fragment}>${parts}</${React.Fragment}>`;
  }

  // Lines of text → paragraphs and "- " bullet lists, the shape Claude Code prints.
  function Prose(props) {
    var lines = String(props.text || "").split("\n");
    var out = [], list = null, k = 0;
    function flush() {
      if (list) { out.push(html`<ul class="cu-list" key=${k++}>${list}</ul>`); list = null; }
    }
    lines.forEach(function (line) {
      var b = /^\s*[-•]\s+(.*)$/.exec(line);
      if (b) { (list = list || []).push(html`<li key=${k++}><${Inline} text=${b[1]} /></li>`); return; }
      flush();
      if (line.trim() === "") out.push(html`<div class="cu-gap" key=${k++}></div>`);
      else out.push(html`<p class="cu-p" key=${k++}><${Inline} text=${line} /></p>`);
    });
    flush();
    return html`<div class="cu-prose">${out}</div>`;
  }

  // ── Terminal chrome ──
  function Terminal(props) {
    return html`<section class="cu-terminal" aria-label=${props.title || "Claude Code session"}>
      <div class="cu-titlebar"><span class="cu-dot cu-dot-r"></span><span class="cu-dot cu-dot-y"></span><span class="cu-dot cu-dot-g"></span>
        <span class="cu-titlebar-text">${props.title || "claude"}</span></div>
      <div class="cu-screen">${props.children}</div>
    </section>`;
  }

  // ── Transcript blocks ──
  function UserPrompt(props) {
    return html`<div class="cu-user"><span class="cu-glyph">›</span><div><${Prose} text=${props.text} /></div></div>`;
  }

  function AssistantText(props) {
    return html`<div class="cu-assistant"><span class="cu-glyph cu-fg">●</span><div><${Prose} text=${props.text} /></div></div>`;
  }

  function ToolCall(props) {
    return html`<div class="cu-tool"><span class="cu-glyph cu-ok">●</span>
      <div><strong>${props.name}</strong>${props.args ? html`<span class="cu-dim">(${props.args})</span>` : null}</div></div>`;
  }

  function ToolResult(props) {
    return html`<div class="cu-result"><span class="cu-glyph cu-dim">⎿</span><div class="cu-dim"><${Prose} text=${props.text} /></div></div>`;
  }

  function Spinner(props) {
    return html`<div class="cu-spinner"><span class="cu-glyph cu-accent">✻</span>
      <div><span class="cu-accent">${String(props.verb || "Thinking").replace(/(…|\.\.\.)+$/, "")}…</span>${props.meta ? html` <span class="cu-dim">(${props.meta})</span>` : null}</div></div>`;
  }

  function Note(props) {
    return html`<div class="cu-note"><span class="cu-glyph cu-dim">✻</span><div class="cu-dim">${props.text}</div></div>`;
  }

  function Recap(props) {
    return html`<div class="cu-recap"><span class="cu-glyph cu-dim">※</span>
      <div><strong class="cu-dim">recap:</strong> <em class="cu-dim"><${Inline} text=${props.text} /></em></div></div>`;
  }

  var TASK_MARK = { pending: "□", in_progress: "■", completed: "✔", blocked: "■" };
  function TaskList(props) {
    var tasks = props.tasks || [];
    // With no title it hangs under the spinner line above it, the way Claude Code prints it.
    return html`<div class=${props.title ? "cu-tasks" : "cu-tasks cu-tasks-attached"}>
      ${props.title ? html`<div class="cu-tasks-title"><span class="cu-accent">✻</span> ${props.title}</div>` : null}
      <ul>${tasks.map(function (t, i) {
        var status = t.status || "pending";
        return html`<li key=${i} class=${"cu-task cu-task-" + status}>
          <span class="cu-elbow">${i === 0 ? "⎿" : ""}</span><span class="cu-task-mark">${TASK_MARK[status] || "□"}</span>
          <span><${Inline} text=${t.title} />${t.note ? html` <span class="cu-dim">› ${t.note}</span>` : null}</span></li>`;
      })}</ul>
      ${props.summary ? html`<div class="cu-dim cu-tasks-summary">… ${String(props.summary).replace(/^(…|\.\.\.)\s*/, "")}</div>` : null}</div>`;
  }

  // Claude stops to ask: a header chip, the question, numbered options (one selected), a hint.
  // With "answer" set it shows the answered form instead: the question and the chosen option.
  function Question(props) {
    var options = props.options || [];
    if (props.answer) {
      return html`<div class="cu-question cu-question-answered">
        <div class="cu-dim">User answered Claude's question:</div>
        <div class="cu-qa"><span class="cu-dim">·</span> <${Inline} text=${props.question || ""} /> <span class="cu-dim">→</span> <strong>${props.answer}</strong></div></div>`;
    }
    return html`<div class="cu-question">
      ${props.header ? html`<span class="cu-chip">${props.header}</span>` : null}
      <div class="cu-q"><strong><${Inline} text=${props.question || ""} /></strong></div>
      <ol class="cu-options">${options.map(function (o, i) {
        var on = props.selected === i + 1;
        return html`<li key=${i} class=${on ? "cu-option cu-option-on" : "cu-option"}>
          <span class="cu-option-mark">${on ? "›" : " "}</span>
          <span>${i + 1}. <strong><${Inline} text=${o.label} /></strong>${o.recommended ? html` <span class="cu-dim">(Recommended)</span>` : null}
            ${o.description ? html`<div class="cu-dim"><${Inline} text=${o.description} /></div>` : null}</span></li>`;
      })}</ol>
      <div class="cu-dim">${props.hint || "Enter to select · ↑/↓ to navigate · Esc to cancel"}</div></div>`;
  }

  function PromptInput(props) {
    return html`<div class="cu-input"><span class="cu-glyph">›</span><span>${props.text || ""}</span><span class="cu-cursor"></span></div>`;
  }

  // segments: [{text, tone: "path"|"branch"|"model"|"meter"|"cost"|"dim"}], meter: {pct}
  function StatusLine(props) {
    var segs = props.segments || [];
    return html`<div class="cu-status">${segs.map(function (s, i) {
      return html`<${React.Fragment} key=${i}>${i ? html`<span class="cu-sep">│</span>` : null}
        ${s.tone === "meter" ? html`<${Meter} pct=${s.pct} label=${s.text} />` : html`<span class=${"cu-tone-" + (s.tone || "dim")}>${s.text}</span>`}
      </${React.Fragment}>`;
    })}${props.right ? html`<span class="cu-status-right cu-dim">${props.right}</span>` : null}</div>`;
  }

  function Meter(props) {
    var pct = Math.max(0, Math.min(100, Number(props.pct) || 0));
    return html`<span class="cu-meter"><span class="cu-meter-bar"><span style=${{ width: pct + "%" }}></span></span> <span>${props.label || pct + "%"}</span></span>`;
  }

  // mode: "auto" | "plan" | "accept-edits" | null
  function Footer(props) {
    var label = { auto: "auto mode on", plan: "plan mode on", "accept-edits": "accept edits on" }[props.mode];
    return html`<div class="cu-footer">${label ? html`<span class="cu-mode">⏵⏵ ${label}</span> ` : null}<span class="cu-dim">${props.text || ""}</span></div>`;
  }

  function Divider() { return html`<hr class="cu-divider" />`; }

  // ── Page furniture ──
  function TechniqueHeader(props) {
    var t = props.technique || {};
    return html`<header class="cu-header">
      ${t.mechanism ? html`<span class="cu-tag">${t.mechanism}</span>` : null}
      <h1>${t.title || "Untitled technique"}</h1>
      ${t.why ? html`<p class="cu-lede"><${Inline} text=${t.why} /></p>` : null}
      <div class="cu-howto">
        ${t.when ? html`<div><h2>When to use it</h2><p><${Inline} text=${t.when} /></p></div>` : null}
        ${t.how && t.how.length ? html`<div><h2>How to reproduce it</h2><ol>${t.how.map(function (s, i) {
          return html`<li key=${i}><${Inline} text=${s} /></li>`; })}</ol></div>` : null}
      </div></header>`;
  }

  function ScreenshotCompare(props) {
    if (!props.src) return null;
    return html`<details class="cu-compare"><summary>Compare with the original screenshot${props.taken ? " (" + props.taken + ")" : ""}</summary>
      <img src=${props.src} alt=${props.alt || "Original screenshot"} loading="lazy" /></details>`;
  }

  // ── Block registry: spec block type → component ──
  var BLOCKS = {
    user_prompt: function (b) { return html`<${UserPrompt} text=${b.text} />`; },
    assistant_text: function (b) { return html`<${AssistantText} text=${b.text} />`; },
    tool_call: function (b) { return html`<${ToolCall} name=${b.name} args=${b.args} />`; },
    tool_result: function (b) { return html`<${ToolResult} text=${b.text} />`; },
    spinner: function (b) { return html`<${Spinner} verb=${b.verb} meta=${b.meta} />`; },
    note: function (b) { return html`<${Note} text=${b.text} />`; },
    recap: function (b) { return html`<${Recap} text=${b.text} />`; },
    task_list: function (b) { return html`<${TaskList} title=${b.title} tasks=${b.tasks} summary=${b.summary} />`; },
    question: function (b) { return html`<${Question} header=${b.header} question=${b.question} options=${b.options}
      selected=${b.selected} hint=${b.hint} answer=${b.answer} />`; },
    prompt_input: function (b) { return html`<${PromptInput} text=${b.text} />`; },
    statusline: function (b) { return html`<${StatusLine} segments=${b.segments} right=${b.right} />`; },
    footer: function (b) { return html`<${Footer} mode=${b.mode} text=${b.text} />`; },
    divider: function () { return html`<${Divider} />`; }
  };

  function Block(props) {
    var render = BLOCKS[props.block.type];
    if (!render) {
      // Loud on purpose: the fix is a new component in this file, not markup in the page.
      return html`<div class="cu-missing">No component for block type "${props.block.type}". Add one to claude-ui.js.</div>`;
    }
    // Each block sits in one .cu-block, which carries the spacing between blocks and a stable
    // anchor for page comments (<slug>:b<index>), so a thread stays on its block across re-renders.
    var b = props.block;
    var attached = b.type === "task_list" && !b.title;
    return html`<div class=${"cu-block cu-block-" + b.type + (attached ? " cu-block-attached" : "") + (props.focused ? " cu-block-focus" : "")}
      data-comment-id=${props.commentId || null}>${render(b)}</div>`;
  }

  // The back story: how the technique came up, in prose. Optional; written from the session.
  function Backstory(props) {
    if (!props.text) return null;
    return html`<section class="cu-backstory"><h2>The back story</h2><${Prose} text=${props.text} /></section>`;
  }

  // Internal view only: what the post view replaces, so the redaction can be checked.
  function RedactionTable(props) {
    var rows = props.rows || [];
    return html`<section class="cu-internal-panel"><h2>Replaced in the post view (${rows.length})</h2>
      ${rows.length ? html`<table class="cu-redactions"><thead><tr><th>Here</th><th>In the post</th></tr></thead>
        <tbody>${rows.map(function (r, i) {
          return html`<tr key=${i}><td><code>${r.find}</code></td><td><code>${r.replace || "(removed)"}</code></td></tr>`; })}</tbody></table>`
        : html`<p class="cu-dim-text">Nothing is replaced. The post view shows this page as is.</p>`}</section>`;
  }

  // Internal view only: the Claude Code session the screenshot came from.
  function SessionLink(props) {
    var s = props.session;
    return html`<section class="cu-internal-panel"><h2>Source session</h2>
      ${s ? html`<dl class="cu-session">
          ${s.title ? html`<dt>Title</dt><dd>${s.title}</dd>` : null}
          <dt>When</dt><dd>${s.timestamp}</dd>
          ${s.cwd ? html`<dt>Folder</dt><dd><code>${s.cwd}</code></dd>` : null}
          <dt>Transcript</dt><dd><a href=${"file://" + encodeURI(s.path)}><code>${s.path}</code></a></dd>
          ${s.uuid ? html`<dt>Message</dt><dd><code>${s.uuid}</code></dd>` : null}
        </dl>`
        : html`<p class="cu-dim-text">No session found. Run find_session.py; sessions older than 30 days are usually deleted.</p>`}</section>`;
  }

  // The transcript blocks, each with its comment anchor. Focus blocks are marked. With trim (post
  // view, post.trim) only the focus blocks show, and a dim ⋯ line stands where blocks were cut.
  function screenBlocks(spec, allowTrim) {
    var blocks = spec.blocks || [];
    var focus = (spec.focus && spec.focus.blocks) || [];
    var trim = allowTrim && spec.post && spec.post.trim && focus.length;
    var out = [], last = -1;
    blocks.forEach(function (b, i) {
      var on = focus.indexOf(i) >= 0;
      if (trim && !on) return;
      if (trim && i !== last + 1) out.push(html`<div key=${"cut" + i} class="cu-cut cu-dim">⋯</div>`);
      out.push(html`<${Block} key=${i} block=${b} focused=${on} commentId=${spec.slug ? spec.slug + ":b" + i : null} />`);
      last = i;
    });
    if (trim && last !== blocks.length - 1) out.push(html`<div key="cut-end" class="cu-cut cu-dim">⋯</div>`);
    return out;
  }

  // Hub: the plan for this technique's post. The focus (confirmed, or a prompt to set one by
  // commenting on a terminal line), the status, Claude's suggestions waiting to be confirmed,
  // the fetched context, and a link to the post preview. Every part is a comment anchor.
  function PostPlan(props) {
    var spec = props.spec || {}, slug = spec.slug || "";
    var focus = spec.focus || {}, ctx = spec.context || {};
    var lines = (focus.blocks || []).map(function (i) { return i + 1; });
    return html`<section class="cu-plan" aria-label="Post plan">
      <div class="cu-plan-head"><h2>Post plan</h2><${StatusChip} status=${spec.status} />
        <a class="cu-plan-preview" href=${"../post/" + slug + ".html"}>Post preview →</a></div>
      <div class="cu-plan-focus" data-comment-id=${slug + ":focus"}>
        ${focus.line && focus.confirmed
          ? html`<p><span class="cu-point-label">The point</span> <${Inline} text=${focus.line} /></p>`
          : html`<p class="cu-dim-text">No focus yet. Comment on a terminal line ("this is the point"), or on this line with the wording.</p>`}
        ${lines.length ? html`<p class="cu-dim-text">Shown by block${lines.length === 1 ? "" : "s"} ${lines.join(", ")}${spec.post && spec.post.trim ? "; the post shows only these" : ""}.</p>` : null}
      </div>
      ${ctx.suggested_focus || ctx.suggested_backstory || (focus.line && !focus.confirmed) ? html`<div class="cu-plan-suggested" data-comment-id=${slug + ":suggested"}>
          <h3>Suggested, not confirmed</h3>
          ${focus.line && !focus.confirmed ? html`<p><strong>Focus:</strong> <${Inline} text=${focus.line} /></p>` : ctx.suggested_focus ? html`<p><strong>Focus:</strong> <${Inline} text=${ctx.suggested_focus} /></p>` : null}
          ${ctx.suggested_backstory ? html`<p><strong>Back story:</strong> <${Inline} text=${ctx.suggested_backstory} /></p>` : null}
          <p class="cu-dim-text">Reply "yes" on this to use it.</p></div>` : null}
      <div class="cu-plan-context" data-comment-id=${slug + ":context"}>
        ${ctx.fetched
          ? html`<p class="cu-dim-text">Context fetched ${ctx.fetched} from ${(ctx.sources || []).join(", ")}${spec.context_href ? html` · <a href=${spec.context_href}>context/${slug}.md</a>` : null}</p>`
          : html`<p class="cu-dim-text">No context fetched yet. Comment "fetch what led here" to get it.</p>`}
      </div>
    </section>`;
  }

  // view: "internal" (faithful, for checking) | "post" (redacted, shareable). Defaults to post.
  function Page(props) {
    var spec = props.spec || {};
    var src = spec.source || {};
    var internal = (props.view || spec.view) === "internal";
    var terminal = html`<${Terminal} title=${spec.terminal_title}>${screenBlocks(spec, !internal)}</${Terminal}>`;
    if (!internal) {
      return html`<main class="cu-page cu-post">
        ${props.backHref ? html`<a class="cu-back" href=${props.backHref}>← All techniques</a>` : null}
        <${TechniqueHeader} technique=${spec.technique} />
        <${Backstory} text=${spec.backstory} />
        ${spec.focus && spec.focus.line ? html`<p class="cu-point" data-comment-id=${spec.slug + ":focus"}><span class="cu-point-label">The point</span> <${Inline} text=${spec.focus.line} /></p>` : null}
        ${terminal}
      </main>`;
    }
    return html`<main class="cu-page cu-internal">
      <div class="cu-banner">Internal validation view: real names and values. Share the post view instead.</div>
      ${props.backHref ? html`<a class="cu-back" href=${props.backHref}>← All techniques</a>` : null}
      <${TechniqueHeader} technique=${spec.technique} />
      <${PostPlan} spec=${spec} />
      <${Backstory} text=${spec.backstory} />
      <div class="cu-side-by-side">
        <div><h2 class="cu-col-title">Recreation</h2>${terminal}</div>
        ${src.image ? html`<div><h2 class="cu-col-title">Original screenshot${src.taken ? " (" + src.taken + ")" : ""}</h2>
          <a href=${src.image}><img class="cu-original" src=${src.image} alt="Original screenshot" /></a></div>` : null}
      </div>
      <p class="cu-credit">Recreated from a real Claude Code session${src.taken ? " on " + src.taken : ""}. Names and numbers are stand-ins.
        ${src.session && src.session.path ? html`<br />Session: <a href=${"file://" + encodeURI(src.session.path)}><code>${src.session.path}</code></a>` : null}</p>
      <${RedactionTable} rows=${spec.applied_redactions} />
      <${SessionLink} session=${src.session} />
    </main>`;
  }

  // ── Gallery ──
  // Where a technique stands on its way to a post (hub). idea → focused → drafting → ready → posted.
  var STATUSES = ["idea", "focused", "drafting", "ready", "posted"];
  function StatusChip(props) {
    var s = STATUSES.indexOf(props.status) >= 0 ? props.status : "idea";
    return html`<span class=${"cu-status-chip cu-status-" + s}>${s}</span>`;
  }

  function TechniqueCard(props) {
    var c = props.card;
    return html`<a class="cu-card" href=${c.href} data-comment-id=${c.slug || null}>
      ${c.image ? html`<img src=${c.image} alt="" loading="lazy" />` : html`<div class="cu-card-blank"></div>`}
      <div class="cu-card-body"><span class="cu-tag">${c.mechanism || "technique"}</span>${c.status ? html` <${StatusChip} status=${c.status} />` : null}
        <h3>${c.title}</h3>${c.focus ? html`<p class="cu-card-focus">${c.focus}</p>` : c.why ? html`<p>${c.why}</p>` : null}
        ${c.taken ? html`<span class="cu-dim cu-card-date">${c.taken}</span>` : null}</div></a>`;
  }

  function Gallery(props) {
    var cards = props.cards || [];
    var mechanisms = Array.from(new Set(cards.map(function (c) { return c.mechanism || "technique"; }))).sort();
    var state = React.useState("all"), filter = state[0], setFilter = state[1];
    var shown = cards.filter(function (c) { return filter === "all" || (c.mechanism || "technique") === filter; });
    return html`<main class="cu-page cu-gallery">
      <header class="cu-header"><h1>${props.title || "Claude techniques"}</h1>
        <p class="cu-lede">${cards.length} technique${cards.length === 1 ? "" : "s"} recreated from screenshots.</p>
        ${props.links && props.links.length ? html`<nav class="cu-links">${props.links.map(function (l) {
          return html`<a key=${l.href} href=${l.href}>${l.label}</a>`; })}</nav>` : null}</header>
      <div class="cu-filters" role="group" aria-label="Filter by mechanism">
        ${["all"].concat(mechanisms).map(function (m) {
          return html`<button key=${m} type="button" aria-pressed=${filter === m} onClick=${function () { setFilter(m); }}>${m}</button>`; })}
      </div>
      <div class="cu-cards">${shown.map(function (c) { return html`<${TechniqueCard} key=${c.href} card=${c} />`; })}</div>
    </main>`;
  }

  // Hub: everything waiting on a person, in sections. Each item links to its page and is a
  // comment anchor (<slug>), so "skip this one" can be said right here.
  function Waiting(props) {
    var sections = (props.sections || []).filter(function (s) { return (s.items || []).length; });
    var total = sections.reduce(function (n, s) { return n + s.items.length; }, 0);
    return html`<main class="cu-page cu-waiting">
      ${props.backHref ? html`<a class="cu-back" href=${props.backHref}>← All techniques</a>` : null}
      <header class="cu-header"><h1>${props.title || "Waiting on you"}</h1>
        <p class="cu-lede">${total ? total + " thing" + (total === 1 ? "" : "s") + " waiting." : "Nothing waiting."}</p></header>
      ${sections.map(function (s) {
        return html`<section key=${s.key} class="cu-wait-section"><h2>${s.title} <span class="cu-dim-text">${s.items.length}</span></h2>
          ${s.hint ? html`<p class="cu-dim-text">${s.hint}</p>` : null}
          <ul class="cu-wait-list">${s.items.map(function (it, i) {
            return html`<li key=${i} data-comment-id=${it.slug || null}><a href=${it.href}>${it.title}</a>${it.detail ? html` <span class="cu-dim-text">· <${Inline} text=${it.detail} /></span>` : null}</li>`; })}</ul></section>`;
      })}
    </main>`;
  }

  // ── Catalog: one sample per block type, so a library change is visible in one place ──
  var SAMPLES = [
    { type: "user_prompt", text: "can we have a hook that runs the linter after every edit?" },
    { type: "spinner", verb: "Spelunking", meta: "20s · ↓ 894 tokens · thinking with medium effort" },
    { type: "tool_call", name: "Bash", args: "make lint" },
    { type: "tool_result", text: "12 files checked, 0 problems" },
    { type: "assistant_text", text: "Done. The linter now runs after each edit.\n\n**What changed:**\n- A `PostToolUse` hook in `.claude/settings.json`\n- It runs `make lint` on the edited file only" },
    { type: "note", text: "Baked for 2m 10s · done 9:54 AM" },
    { type: "recap", text: "I added a lint hook. Next, you decide whether it should also run on commit." },
    { type: "task_list", title: "T3 Wire the lint hook… (7s)", tasks: [
      { id: "T1", title: "Find the lint command", status: "completed" },
      { id: "T2", title: "Add the hook", status: "in_progress" },
      { id: "T3", title: "Document it", status: "pending", note: "blocked by T2" }], summary: "+2 pending, 5 completed" },
    { type: "question", header: "Hook", question: "Should the lint hook also run on commit?", selected: 1, options: [
      { label: "Edits only", description: "Fast, and commits stay quick.", recommended: true },
      { label: "Edits and commits", description: "Catches anything an edit missed." }] },
    { type: "question", question: "Should the lint hook also run on commit?", answer: "Edits only" },
    { type: "divider" },
    { type: "prompt_input", text: "" },
    { type: "statusline", segments: [{ text: "workspace/example-app", tone: "path" }, { text: "feature/lint-hook", tone: "branch" },
      { text: "Opus (1M context)", tone: "model" }, { text: "42%", tone: "meter", pct: 42 }], right: "38% until auto-compact" },
    { type: "footer", mode: "auto", text: "(shift+tab to cycle)" }
  ];

  function Catalog() {
    return html`<main class="cu-page">
      <header class="cu-header"><span class="cu-tag">catalog</span><h1>Claude UI components</h1>
        <p class="cu-lede">Every block type a technique spec can use, rendered from claude-ui.js.</p></header>
      ${SAMPLES.map(function (b, i) {
        return html`<section class="cu-sample" key=${i}><h2><code>${b.type}</code></h2>
          <${Terminal} title=${b.type}><${Block} block=${b} /></${Terminal}></section>`; })}
    </main>`;
  }

  function readJSON(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  // A pre-rendered page (prerender.js) already holds the markup, so React hydrates it rather
  // than drawing it again. The props must match the ones prerender.js used.
  function mount(el, Component, props) {
    var tree = html`<${Component} ...${props || {}} />`;
    if (el.firstElementChild) window.ReactDOM.hydrateRoot(el, tree);
    else window.ReactDOM.createRoot(el).render(tree);
  }

  window.ClaudeUI = {
    html: html, Inline: Inline, Prose: Prose, Terminal: Terminal,
    UserPrompt: UserPrompt, AssistantText: AssistantText, ToolCall: ToolCall, ToolResult: ToolResult,
    Spinner: Spinner, Note: Note, Recap: Recap, TaskList: TaskList, PromptInput: PromptInput,
    StatusLine: StatusLine, Meter: Meter, Footer: Footer, Divider: Divider,
    TechniqueHeader: TechniqueHeader, StatusChip: StatusChip, STATUSES: STATUSES, PostPlan: PostPlan, Waiting: Waiting, ScreenshotCompare: ScreenshotCompare,
    Block: Block, BLOCKS: BLOCKS, Page: Page, TechniqueCard: TechniqueCard, Gallery: Gallery,
    Catalog: Catalog, SAMPLES: SAMPLES, readJSON: readJSON, mount: mount
  };
})();
