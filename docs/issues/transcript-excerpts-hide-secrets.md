# Transcript excerpts hide passwords and keys

## What went wrong

The technique-manager scripts that quote transcripts printed whatever was in them. These are
`search-transcripts` snippets, `research-backstory` excerpts and `find_session` matches. One
technique's session (2026-10-08) had passwords pasted into a prompt as `NAME_PASSWORD=value`
lines. Fetching that technique's back story printed four of them into the terminal and into a
scratch file. They were assumed rotated, but they should never have been shown.

## What changed

`recreate-technique/scripts/hide_secrets.py` has one function, `hide(text)`. Every script that
prints transcript text calls it first:

- `remote_sessions.py snippets` hides the whole line before cutting the window, so a secret at
  the window's edge is still caught whole.
- `fetch_context.py` hides each excerpt before cutting it to `--max-chars`.
- `find_session.py` hides the prompt it prints with a match.
- `scan_privacy.py` reports a `secret` kind with the value's outline only (`a`/`A`/`9`/`#`). That
  also makes `render_page.py` refuse to write a post that still holds a secret.

A hidden value becomes `[hidden <kind>]`. The label in front of it stays, so the sentence still
reads.

## The rules, and why they look this way

1. **Known token formats**: AWS, GitHub, Slack, Anthropic/OpenAI `sk-`, Google, Stripe, Shopify,
   JWT, bearer tokens, private key blocks, and `user:password@` in a URL.
2. **Labelled values**: `password: X`, `API_KEY=X`, `"client_secret": "X"`, `secret is X`. This is
   the rule that caught the real leak; all of the 2026-10-08 values were labelled.
3. **Random-looking words**: a word with every kind of character, or a long mix of cases and
   digits, where the case flips between letters about as often as in a random string.

The first version hid far too much. It was measured on three ordinary sessions (377k transcript
lines) with `hide_secrets.py --show-hidden`, which prints the outline of each hidden word, never
the value:

| Version | random-looking word | labelled secret |
|---|---|---|
| First: any word with lower, upper, digit and symbol | 169,865 | 1,066 |
| Case must flip often; skip ids, times, colors, markdown | 413 | 1,066 |
| Label must be a whole word; plain lowercase after `is`/`:` is prose | 413 | 211 |

What the first version wrongly hid:

- Times such as `9:45PM` and ISO timestamps.
- Message, request and tool-call ids (`msg_…`, `req_…`, `toolu_…`).
- Hex colors, `**bold**` markdown and camelCase names.
- For the labelled rule, `pass` matched "PASS:" in test output, "passed", "DashPass" and
  "LastPass". Sentences like "the password is stored…" and "no real secret was involved." also
  matched.

The leaking session was re-checked after each change. It still hid every pasted value, and the
values the audit lets through there are environment variable names.

## What it does not catch

- A human-chosen password typed with no label and no random look (`Summer2024` alone).
- A lowercase dictionary word after `password:`. That reads as prose, and hiding prose costs
  more than it saves.

It errs toward hiding everything else. A wrongly hidden word costs one word in an excerpt; a
missed secret costs a rotation.

## Checks

- `python3 plugins/technique-manager/skills/recreate-technique/scripts/test_hide_secrets.py`:
  what it hides, what it leaves alone, and that nothing it reports carries a value. Its fake
  tokens are joined from pieces at run time, so gitleaks does not flag the test file.
- `hide_secrets.py <session.jsonl> --show-hidden`: re-measure over-hiding after a rule change.
