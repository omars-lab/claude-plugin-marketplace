# guardrail-manager

Advisory hooks, gated by a conf file per repo, for two failure modes that keep recurring:
several Claude Code sessions sharing one checkout, and a review step that a session should
have run but did not — plus two on-by-default guards: one denies any git command resolving a
conflict with `-X ours/theirs`, `-s ours` or `checkout --ours/--theirs`; the other
(`branch-sprawl-guard`) checks a `git worktree add` once the repo already has a budget's worth
of working trees. If some of them are finished (nothing unsaved, work pushed, no other session in
them) it denies with the commands to reuse or remove them, so the session cleans up by itself;
when every tree holds live work it lets the add through and tells the session what would land
each tree, without asking you. A new branch inside an existing tree passes.
Opt out or retune it with `.claude/hooks/branch-sprawl.conf` (`ENABLED=0`, `MAX_WORKTREES=N`,
`DECISION=nudge|ask|deny`, `IN_USE_MINUTES=N`).

`merge-and-continue` is a Stop hook for repos where merging your own PRs is already
approved: when the session's last message asks "shall I merge?" or reports a PR left open,
it sends the session back to merge once the PR is CLEAN and carry on with the next item. It
fires once per stop and only in repos whose name matches `REPO_REGEX` in
`merge-and-continue.conf` (see `examples/`).

Run `/guardrail-manager:introduce` for the full capability list. That skill is the
authoritative reference. `/guardrail-manager:configure-guardrails` audits a repo and writes
the conf files.

`git-settings-guard` keeps a checkout's own git settings sane. At session start, and before git
commands, it says when `core.bare` is true or `core.hooksPath` is absolute, outside the repo
or missing, and gives the fix. It denies a `git config` that would set either one wrong.

Every advisory hook is a no-op until a conf exists; `block-git-ours-theirs`,
`branch-sprawl-guard` and `git-settings-guard` are the exceptions (on by default, opt out with
`ENABLED=0` in their conf). All exit 0 and have a `--selftest`:

```
make test-guardrail-hooks
```

A passing selftest is not proof of install. After writing a conf, prove the hook fires with a
throwaway headless probe from that repo (`claude -p "run: echo probe" --max-turns 1`) and read
the `hook_success` entries in the probe transcript; `configure-guardrails` has the VERIFY steps.
