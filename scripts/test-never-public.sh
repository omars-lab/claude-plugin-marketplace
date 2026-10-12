#!/bin/bash
# Self-test for scripts/check-never-public.sh and the never-public parts of the GitHub sync.
# Builds a throwaway "internal" repo and a local bare "github" remote in a temp folder,
# with an invented private list, so it never touches this repo or the real GitHub.
# Usage: ./scripts/test-never-public.sh   (or: make test-never-public)

set -euo pipefail
export LC_ALL=en_US.UTF-8

SRC=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
FAILS=0
ok()   { echo "  ok   $1"; }
fail() { echo "  FAIL $1"; FAILS=$((FAILS + 1)); }
expect() {  # expect <0|1> <label> <command...>
    local want="$1" label="$2"; shift 2
    local got=0; "$@" >/dev/null 2>&1 || got=$?
    [ "$got" = "$want" ] && ok "$label" || fail "$label (exit $got, wanted $want)"
}

git init -q --bare -b main "$T/github.git"
git init -q -b main "$T/internal"
cd "$T/internal"
git config user.name "Work Person"; git config user.email "work@example.com"
mkdir -p scripts .claude
cp "$SRC/check-never-public.sh" "$SRC/never-public.patterns" "$SRC/sync-to-github.sh" "$SRC/sync-to-github-init.sh" scripts/
printf '# invented test list\nAcmeCorp\nwiki\\.acme\\.example\n' > .claude/never-public.txt
echo "readme" > README.md
git add -A; git commit -q -m "start"
CHECK=scripts/check-never-public.sh

echo "== staged lines (what pre-commit runs) =="
try_staged() {  # try_staged <0|1> <label> <line>
    echo "$3" > probe.txt; git add probe.txt
    expect "$1" "$2" "$CHECK" --staged
    git rm -q --cached probe.txt; rm -f probe.txt
}
try_staged 1 "private name is blocked"              "notes from my time at AcmeCorp"
try_staged 1 "private name is blocked in any case"  "ACMECORP"
try_staged 1 "Tailscale host name is blocked"       "http://box.tail1a2b3c.ts.net:8080/x"
try_staged 1 "Tailscale IPv4 address is blocked"    "ssh 100.101.5.6"
try_staged 1 "private address is blocked"           "see https://wiki.acme.example/page"
try_staged 1 "private address in a regex is blocked" "r'|wiki\\.acme\\.example'"
try_staged 1 "double-escaped address is blocked"    "\"wiki\\\\.acme\\\\.example\""
try_staged 1 "Tailscale host in a regex is blocked" "r'box\\.tail1a2b3c\\.ts\\.net'"
try_staged 0 "shopping link passes"                 "https://www.amazon.com/dp/B01"
try_staged 0 "private IP outside Tailscale passes"  "ssh 10.0.0.1 or 100.2.3.4"
try_staged 0 "generic .ts.net rule passes"          "r'|\\.ts\\.net(?:[:/]|$)'"
mkdir -p notes; echo "x" > notes/AcmeCorp.md; git add notes
expect 1 "private name in a file NAME is blocked" "$CHECK" --staged
git rm -q -r --cached notes; rm -rf notes

echo "== first sync (full rewrite) =="
echo RESET | bash scripts/sync-to-github-init.sh "$T/github.git" github "Pub" "pub@example.com" >"$T/init.log" 2>&1 \
    || { cat "$T/init.log"; exit 1; }
git fetch -q github main
[ -z "$(git ls-tree -r --name-only github/main -- .claude)" ] && ok "private list is not on github" || fail "private list reached github"

echo "== a clean commit is published as itself =="
echo "code 1" > code.txt; git add code.txt; git commit -q -m "add code"
bash scripts/sync-to-github.sh "$T/github.git" github "Pub" "pub@example.com" >"$T/s1.log" 2>&1 \
    || { cat "$T/s1.log"; exit 1; }
git fetch -q github main
[ "$(git log -1 --format=%s github/main)" = "add code" ] && ok "same message on github" || fail "clean commit was not published as itself"

echo "== private text added then removed goes up as one commit =="
before=$(git rev-list --count github/main)
echo "met AcmeCorp" >> code.txt; git add code.txt; git commit -q -m "note about AcmeCorp"
sed -i '' '/AcmeCorp/d' code.txt; echo "code 2" >> code.txt; git add code.txt; git commit -q -m "tidy"
bash scripts/sync-to-github.sh "$T/github.git" github "Pub" "pub@example.com" >"$T/s2.log" 2>&1 \
    || { cat "$T/s2.log"; exit 1; }
git fetch -q github main
[ $(( $(git rev-list --count github/main) - before )) = 1 ] && ok "two commits published as one" || fail "range was not squashed"
[ -z "$(git log -p github/main | grep -i acmecorp || true)" ] && ok "private name nowhere in github history" || fail "private name reached github history"
git log -1 --format=%B github/main | grep -q "subject withheld" && ok "private commit subject withheld" || fail "private subject not withheld"
git log -1 --format=%B github/main | grep -qx -- "- tidy" && ok "clean commit subject kept" || fail "clean subject was withheld too"
[ "$(git show github/main:code.txt)" = "$(git show main:code.txt)" ] && ok "end state matches internal" || fail "end state differs"

echo "== private text still present blocks the sync =="
before_sha=$(git rev-parse github/main)
echo "AcmeCorp again" >> code.txt; git add code.txt; git commit -q -m "oops"
expect 1 "sync refuses to push" bash scripts/sync-to-github.sh "$T/github.git" github "Pub" "pub@example.com"
git fetch -q github main
[ "$(git rev-parse github/main)" = "$before_sha" ] && ok "github unchanged" || fail "github moved"
[ "$(git branch --show-current)" = main ] && ok "back on main" || fail "left on $(git branch --show-current)"
git rev-parse -q --verify __github_sync >/dev/null && fail "sync branch left behind" || ok "sync branch cleaned up"

echo ""
if [ "$FAILS" = 0 ]; then echo "never-public: all checks pass"; else echo "never-public: $FAILS check(s) failed"; exit 1; fi
