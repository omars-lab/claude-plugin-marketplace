# Makefile Targets for Git Submodules

Reference for adding git-submodule support to a Makefile. Use when a repo vendors another repo as a submodule (e.g. a shared `prompts/`, `docs/`, or `lib/` submodule) and you want `make` targets to manage it. Replace `<sub>` with the actual submodule directory name.

## Principles

- **Extend, never replace.** Add targets to the existing Makefile; preserve all original targets and match the existing style.
- **Idempotent targets.** Check current state before acting; safe to run repeatedly.
- **Tabs, not spaces.** Recipe lines MUST be tab-indented. Verify with `make -n <target>`; inspect with `sed -n 'A,Bp' Makefile | cat -e`; fix with `sed -i '' 's/^    /\t/' Makefile`.
- **Always `make help` after changes** and add every new target to `.PHONY`.

## Common submodule problems these targets solve

| Problem | Cause | Fix |
|---|---|---|
| Detached HEAD after update | `git submodule update --remote` checks out a commit, not a branch | `fix-submodule-detached-head` |
| Recursive push does nothing | Only pushes actual commits, not uncommitted changes | commit the submodule ref first, then `push-with-submodules` |
| `git status` hides submodule detail | Not shown by default | `enable-submodule-status` (sets `status.submodulesummary 1`) |

## Target set (generalize `<sub>` and the remote URL)

```makefile
update-<sub>: ## Pull latest changes from the <sub> submodule
	@echo "Updating <sub> submodule..."
	git submodule update --remote <sub>
	@echo "<sub> submodule updated."

enable-submodule-status: ## Show submodule summary in git status
	@if [ "$$(git config --get status.submodulesummary)" != "1" ]; then \
		git config status.submodulesummary 1; \
		echo "Submodule status enabled."; \
	else echo "Already enabled."; fi

enable-recursive-push: ## Push submodule commits on demand
	@if [ "$$(git config --get push.recurseSubmodules)" != "on-demand" ]; then \
		git config --global push.recurseSubmodules on-demand; \
		echo "Recursive submodule pushes enabled."; \
	else echo "Already enabled."; fi

fix-submodule-detached-head: ## Reattach <sub> submodule to its main branch
	@echo "Fixing detached HEAD in <sub>..."
	cd <sub> && git checkout -b main origin/main 2>/dev/null || git checkout main
	@echo "Submodule HEAD fixed."

commit-submodule-updates: ## Commit the <sub> submodule reference change
	@git add <sub>
	@if [ -n "$$(git status --porcelain)" ]; then \
		git commit -m "Update <sub> submodule"; echo "Committed."; \
	else echo "No submodule changes to commit."; fi

push-with-submodules: ## Push commits and submodules recursively
	git push --recurse-submodules=on-demand
```

## Complete update workflow

```bash
make update-<sub>                  # pull latest
make fix-submodule-detached-head   # reattach branch if needed
make commit-submodule-updates      # commit the ref change in the parent
make push-with-submodules          # push everything
```

One-time setup: `make enable-submodule-status && make enable-recursive-push`.

## Agent header note (optional, for the Makefile top)

The existing generate-makefile workflow already prescribes a header + `.PHONY` + standard variables. When submodules are involved, add to the header's guidance:
- Use `git add .` (or `git add <sub>`) to stage submodule reference changes.
- Submodule updates require committing the reference change in the parent repo.

## Debugging

```bash
git submodule status
git config --file .gitmodules --list
cd <sub> && git remote -v && git branch -a && git log --oneline -3
```
