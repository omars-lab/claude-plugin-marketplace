#!/bin/bash

# ── Configuration ──────────────────────────────────────────────────────────────
BAR_STYLE="blocks"       # "blocks" (▓█░)  or  "circles" (●●○)
BAR_WIDTH=20             # number of segments  (10 or 20 recommended)
SHOW_LEGEND=true         # legend: ▓=cached  █=ctx  ░=free
SHOW_TOKEN_COUNT=true    # show used_k/max_k token count alongside bar
SHOW_COST=true           # show session cost  $0.12
SHOW_EDIT_ACTIVITY=true  # show +lines/-lines code edit activity
SHOW_GIT=true            # git pipeline: ⎇ branch  ?=untracked  +=staged  ↑=ahead  ✓=clean
CWD_MAX_LEN=30           # truncate cwd to last 2 components when longer than this
# ──────────────────────────────────────────────────────────────────────────────

input=$(cat)
user=$(whoami)
host=$(hostname -s)
cwd=$(echo "$input"       | jq -r '.workspace.current_dir // .cwd // ""')

# Shorten CWD: replace $HOME with ~, then abbreviate to …/parent/dir if still long
cwd_short="${cwd/#$HOME/~}"
if [ "${#cwd_short}" -gt "$CWD_MAX_LEN" ]; then
  cwd_short="…/$(basename "$(dirname "$cwd")")/$(basename "$cwd")"
fi
model=$(echo "$input"     | jq -r '.model.display_name // ""')
used_pct=$(echo "$input"  | jq -r '.context_window.used_percentage // empty')
cost=$(echo "$input"      | jq -r '.cost.total_cost_usd // empty')
lines_added=$(echo "$input"   | jq -r '.cost.total_lines_added // 0')
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
max_ctx=$(echo "$input"   | jq -r '.context_window.context_window_size // 200000')
input_tok=$(echo "$input"    | jq -r '.context_window.current_usage.input_tokens // 0')
cache_read=$(echo "$input"   | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')
cache_create=$(echo "$input" | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')

# ANSI codes — standard (non-bright) for a muted, pastel feel matching Claude Code
RS='\033[0m'
DIM='\033[2m'
BLUE='\033[34m'       # blue    — user@host
CYAN='\033[36m'       # cyan    — cwd
MAGENTA='\033[35m'    # magenta — cached/MCP-proxy segments
GREEN='\033[32m'      # green   — fresh tokens, low usage
YELLOW='\033[33m'     # yellow  — fresh tokens, medium usage
RED='\033[31m'        # red     — fresh tokens, high usage

# ── Context bar ────────────────────────────────────────────────────────────────
ctx_info=""
if [ -z "$used_pct" ] || [ "$used_pct" = "null" ]; then
  # Loading state
  empty_char="░"; [ "$BAR_STYLE" = "circles" ] && empty_char="○"
  placeholder=""
  for i in $(seq 1 "$BAR_WIDTH"); do placeholder="${placeholder}${empty_char}"; done
  ctx_info=" | [${DIM}${placeholder}${RS}] loading..."
else
  pct=$(printf "%.0f" "$used_pct" 2>/dev/null || echo "$used_pct")
  [ "$pct" -gt 100 ] 2>/dev/null && pct=100

  # Fresh-token color scales with usage
  if   [ "$pct" -gt 80 ]; then fc="$RED"
  elif [ "$pct" -gt 60 ]; then fc="$YELLOW"
  else fc="$GREEN"; fi

  # Segment counts
  filled=$(awk -v p="$pct" -v w="$BAR_WIDTH" 'BEGIN{printf "%d", (p/100)*w}')
  empty=$((BAR_WIDTH - filled))
  total_cur=$(( input_tok + cache_read + cache_create ))
  cache_segs=$(awk -v cr="$cache_read" -v cc="$cache_create" -v tot="$total_cur" -v f="$filled" \
    'BEGIN{if(tot>0) printf "%d",(cr+cc)/tot*f; else print 0}')
  fresh_segs=$(( filled - cache_segs ))

  # Chars per style
  if [ "$BAR_STYLE" = "circles" ]; then
    FILL_CACHE="${MAGENTA}●${RS}"
    FILL_FRESH="${fc}●${RS}"
    FILL_EMPTY="${DIM}○${RS}"
  else
    FILL_CACHE="${MAGENTA}▓${RS}"
    FILL_FRESH="${fc}█${RS}"
    FILL_EMPTY="${DIM}░${RS}"
  fi

  bar="["
  for i in $(seq 0 $((BAR_WIDTH - 1))); do
    if   [ "$i" -lt "$cache_segs" ]; then bar="${bar}${FILL_CACHE}"
    elif [ "$i" -lt "$filled" ];     then bar="${bar}${FILL_FRESH}"
    else                                  bar="${bar}${FILL_EMPTY}"
    fi
  done
  bar="${bar}]"

  # Optional token count
  tok_label=""
  if [ "$SHOW_TOKEN_COUNT" = "true" ]; then
    used_k=$(( max_ctx * pct / 100 / 1000 ))
    max_k=$(( max_ctx / 1000 ))
    tok_label=" ${fc}${used_k}k${RS}/${max_k}k"
  fi

  # Optional legend (colors match current bar state)
  legend=""
  if [ "$SHOW_LEGEND" = "true" ]; then
    if [ "$BAR_STYLE" = "circles" ]; then
      legend="  ${DIM}[${MAGENTA}●${RS}${DIM}=cached  ${fc}●${RS}${DIM}=ctx  ○=free]${RS}"
    else
      legend="  ${DIM}[${MAGENTA}▓${RS}${DIM}=cached  ${fc}█${RS}${DIM}=ctx  ░=free]${RS}"
    fi
  fi

  ctx_info=" | ${bar}${tok_label} ${fc}${pct}%${RS}${legend}"
fi

# ── Session cost ───────────────────────────────────────────────────────────────
cost_info=""
if [ "$SHOW_COST" = "true" ] && [ -n "$cost" ] && [ "$cost" != "null" ]; then
  cost_info=" | $(printf '$%.2f' "$cost")"
fi

# ── Edit activity (lines changed = file-edit tool proxy) ───────────────────────
edit_info=""
if [ "$SHOW_EDIT_ACTIVITY" = "true" ] && { [ "$lines_added" -gt 0 ] || [ "$lines_removed" -gt 0 ]; }; then
  edit_info=" | ${GREEN}+${lines_added}${RS} ${RED}-${lines_removed}${RS}"
fi

# ── Git pipeline ───────────────────────────────────────────────────────────────
git_info=""
if [ "$SHOW_GIT" = "true" ] && command -v git &>/dev/null && [ -n "$cwd" ]; then
  branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
  if [ -n "$branch" ]; then
    status_out=$(git -C "$cwd" status --porcelain 2>/dev/null)
    ahead=$(git -C "$cwd" rev-list --count "@{u}..HEAD" 2>/dev/null)
    has_untracked=$(printf '%s' "$status_out" | grep -c '^??')
    has_staged=$(printf '%s' "$status_out" | grep -cE '^[MADRCT]')
    markers=""
    [ "$has_untracked" -gt 0 ] && markers="${markers}${DIM}?${RS}"
    [ "$has_staged"    -gt 0 ] && markers="${markers}${GREEN}+${RS}"
    [ -n "$ahead" ] && [ "$ahead" -gt 0 ] && markers="${markers}${CYAN}↑${ahead}${RS}"
    [ -z "$markers" ] && markers="${DIM}✓${RS}"
    git_info=" | ${DIM}⎇${RS} ${branch} ${markers}"
  fi
fi

# ── Output ─────────────────────────────────────────────────────────────────────
printf '%b\n' "${BLUE}${user}@${host}${RS}:${CYAN}${cwd_short}${RS} | ${model}${ctx_info}${cost_info}${edit_info}${git_info}"
