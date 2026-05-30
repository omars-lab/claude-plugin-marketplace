---
name: install-hooks
description: Install git hooks for secret scanning (gitleaks) and test gates on a repository. Creates pre-commit and pre-push hooks, adds Makefile targets, and optionally creates a project-level secret-scan skill.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, TaskCreate, TaskUpdate
---

# Install Hooks

Installs a complete security and test gate setup on any git repository.

## What Gets Installed

| Component | Purpose |
|-----------|---------|
| `.git/hooks/pre-commit` | Blocks commits if gitleaks not installed; scans staged changes for secrets |
| `.git/hooks/pre-push` | Blocks pushes if gitleaks not installed; runs secret scan + tests; optionally blocks direct pushes to a protected mirror remote |
| Makefile targets | `secret-scan`, `secret-scan-staged`, `install-hooks` |
| `.claude/skills/secret-scan/SKILL.md` | Project-level skill documenting the security setup |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Detect repo type and test target", description: "Identify the repo's language, test framework, and make test target" })
TaskCreate({ subject: "Install gitleaks hooks", description: "Create pre-commit and pre-push hooks" })
TaskCreate({ subject: "Add Makefile targets", description: "Add secret-scan and install-hooks targets" })
TaskCreate({ subject: "Create secret-scan skill", description: "Add .claude/skills/secret-scan/SKILL.md" })
TaskCreate({ subject: "Verify installation", description: "Run hooks and confirm they work" })
```

## Step 1: Detect Repo Type

Read the repo to determine:
- **Language/framework** (Python, Node, Rust, Go, etc.)
- **Existing test target** — check Makefile for `test`, `all-test`, `sim-test`, etc.
- **Existing hooks** — check `.git/hooks/pre-commit` and `.git/hooks/pre-push`
- **Existing security** — check for `secret-scan` in Makefile

```bash
# Detect
ls Makefile pyproject.toml package.json Cargo.toml go.mod 2>/dev/null
grep -E '^[a-zA-Z_-]*test[a-zA-Z_-]*:' Makefile 2>/dev/null
ls .git/hooks/pre-commit .git/hooks/pre-push 2>/dev/null
grep 'secret-scan' Makefile 2>/dev/null
```

If hooks already exist, **read them first** — append our checks only if not already present. Never overwrite existing hooks without asking.

## Step 2: Install Pre-Commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/sh
if ! command -v gitleaks &> /dev/null; then
    echo ""
    echo "ERROR: gitleaks is not installed."
    echo "Install it with: brew install gitleaks"
    echo ""
    echo "Commits are blocked until gitleaks is available."
    echo "This is required to prevent secrets from being committed."
    exit 1
fi
echo "Scanning staged changes for secrets..."
gitleaks protect --staged --verbose
```

Make executable: `chmod +x .git/hooks/pre-commit`

## Step 3: Install Pre-Push Hook

Create `.git/hooks/pre-push`. The test command varies by repo — use what was detected in Step 1.

```bash
#!/bin/sh

# === Secret scan ===
if ! command -v gitleaks &> /dev/null; then
    echo ""
    echo "ERROR: gitleaks is not installed."
    echo "Install it with: brew install gitleaks"
    echo ""
    echo "Pushes are blocked until gitleaks is available."
    exit 1
fi
echo "Running full secret scan before push..."
gitleaks detect --source . --verbose
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Secret scan failed. Push blocked."
    exit 1
fi

# === Tests ===
echo ""
echo "Running tests before push..."
make TEST_TARGET_HERE
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Tests failed. Push blocked."
    echo "Fix failing tests and try again."
    exit 1
fi
echo "Tests passed."
```

Replace `TEST_TARGET_HERE` with the actual test target (e.g., `all-test`, `test`, `sim-test`).

If the repo has **no test target**, skip the test section and only include the secret scan. Note this gap in the output.

Make executable: `chmod +x .git/hooks/pre-push`

## Step 3b: Protected-Remote Guard (opt-in)

Some repos must **not** be pushed to a given remote directly — e.g. a public GitHub mirror that is only meant to be reached through a sanitizing/author-rewriting sync (`make sync-remote`), never a raw `git push github`. A direct push bypasses the rewrite and can leak identity or unreviewed history.

When the repo has such a remote (ask the user, or detect a `sync-remote`/`push-all` Makefile target alongside a remote named `github`), prepend this guard to `.git/hooks/pre-push`. Git passes the **remote name as `$1`** to the pre-push hook:

```sh
# === Protected-remote guard ===
# This repo reaches its public mirror only via `make sync-remote` (author rewrite).
# Block direct pushes to the protected remote.
PROTECTED_REMOTE="github"          # configure per repo
REMOTE_NAME="$1"
if [ "$REMOTE_NAME" = "$PROTECTED_REMOTE" ]; then
    echo ""
    echo "ERROR: Direct push to '$PROTECTED_REMOTE' is blocked."
    echo "This remote is a public mirror — push via the sanitizing sync instead:"
    echo "    make sync-remote        # author-rewriting, content-checked path"
    echo ""
    echo "(If you really mean to bypass, push with --no-verify — and know why.)"
    exit 1
fi
```

Notes:
- Put this **first** in the hook, before the secret scan, so it fails fast.
- `PROTECTED_REMOTE` is per-repo; confirm the remote name with the user (here it's `github`).
- The `--no-verify` escape hatch is intentional — the guard is a safety net against the *accidental* direct push (the common mistake), not a hard lock.
- This complements (does not replace) the secret scan: gitleaks catches credentials, this catches the wrong-destination push.

## Step 4: Add Makefile Targets

Check if these targets already exist. Only add what's missing.

```makefile
secret-scan: ## Scan repo for leaked secrets (requires gitleaks)
	@command -v gitleaks >/dev/null 2>&1 || { echo "Installing gitleaks..."; brew install gitleaks; }
	gitleaks detect --source . --verbose

secret-scan-staged: ## Scan only staged changes (pre-commit style)
	@command -v gitleaks >/dev/null 2>&1 || { echo "Installing gitleaks..."; brew install gitleaks; }
	gitleaks protect --staged --verbose

install-hooks: ## Install git hooks for secret scanning and test gates
	@echo "Installing pre-commit hook..."
	@cp .hooks/pre-commit .git/hooks/pre-commit 2>/dev/null || echo "Creating hook..."
	@chmod +x .git/hooks/pre-commit
	@echo "Installing pre-push hook..."
	@cp .hooks/pre-push .git/hooks/pre-push 2>/dev/null || echo "Creating hook..."
	@chmod +x .git/hooks/pre-push
	@echo "Hooks installed. Commits require gitleaks, pushes require gitleaks + tests."
```

If the repo wants **committable hooks** (so fresh clones get them automatically), also create `.hooks/pre-commit` and `.hooks/pre-push` with the same content, and have `install-hooks` copy from there.

## Step 5: Create Project-Level Skill (Optional)

If the repo has `.claude/skills/`, create `.claude/skills/secret-scan/SKILL.md` documenting:
- What hooks are installed
- What test targets run on push
- How to install gitleaks
- How to reinstall hooks on fresh clones

## Step 6: Verify

```bash
# Verify gitleaks is installed
which gitleaks && gitleaks version

# Verify hooks exist and are executable
ls -la .git/hooks/pre-commit .git/hooks/pre-push

# Verify Makefile targets
make secret-scan

# Test that hooks actually block (optional — stage a dummy secret)
echo "TEST_SECRET=sk_test_1234567890" > /tmp/test-secret.txt
# Don't actually commit this — just verify the hook would catch it
```

## Output

Report what was installed:

```
Repo Security Setup Complete:
  pre-commit: gitleaks staged scan (blocks without gitleaks)
  pre-push:   gitleaks full scan + make TARGET (blocks on failures)
  Makefile:   secret-scan, secret-scan-staged, install-hooks
  Skill:      .claude/skills/secret-scan/SKILL.md

Test target: make TARGET
Hooks enforce: no secrets committed, no untested code pushed
```
