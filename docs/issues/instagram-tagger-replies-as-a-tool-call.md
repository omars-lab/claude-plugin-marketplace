# The Instagram tagger gets its answer through a tool call, not as JSON text

**Where:** `plugins/instagram-manager/skills/tag-saves/scripts/tag_saves.py`, and (until it was
removed, see the last section) `call_tool` in `plugins/instagram-manager/shared/scripts/claude.py`.

## What was tried

The tagger asked Claude Haiku to "reply with one JSON object and nothing else", with a 300-token
cap, and pulled the first `{...}` out of the reply text.

## What happened

On the first real pilot run (165 saves), 142 replies could not be read. Almost every one used
exactly 300 output tokens, and none held a closing brace: the model either wrote text before the
JSON or was still writing when it hit the cap. The 23 that worked were short and fine. A larger
cap would only have made the failures cost more.

The same run also used up the account's API credit. The API then answered every call with
HTTP 400 "credit balance is too low", and the tagger treated each one as a bad reply for that
save. A run that cannot succeed should stop at the first such answer, not blame every save.

## What replaced it

- **A forced tool call.** The request carries one tool, `tag`, with the four lists as its input
  schema, and `tool_choice` makes the model call it. The API returns the fields as data, so there
  is no text to parse and no half-written JSON. A reply cut off at the token cap is reported as
  "reply cut off", not as a parse error. The cap went back to 600.
- **A stop on refusal.** `claude.py` raises `Refused` for 401, 403, or a 400 about credit. The
  tagger stops starting new calls the moment one comes back, saves what it has, and exits with the
  API's message. The saves it did not reach keep their collection tags and are asked on the next
  run, and none of them is marked as a bad reply.

Both are covered by the offline tests in `test_tag_saves.py`.

## Then: scripts stopped calling the model at all

The tool call fixed the replies, but the run still needed an API key with credit, billed apart
from the Claude plan the user already pays for. Two more tries followed, and the second one stuck.

- **`claude -p` per save** (Claude Code's print mode, on the logged-in plan). It worked: no key,
  and the plan covered it. But it started a new Claude Code process for each of thousands of
  saves, each one re-sending the same instructions and topic list, with the script doing the work
  of a session.
- **What replaced it: a plugin agent reading batches.** The model step became
  `agents/save-tagger.md` (Haiku, tools Read and Write). The script no longer calls anything:
  - `tag_saves.py --prepare` writes batch files to the data repo's `.cache/batches/tag/`: the topic
    list, the place list and up to 40 saves or about 60,000 characters each. A save is never split.
    The size comes from the real captions (median 294 characters, 99% under about 2,000), so a
    batch is about 15,000 tokens and sits well inside an agent's context.
  - The Claude Code session starts one agent per batch, in waves of at most 4. Each writes an
    answers file beside its batch.
  - `tag_saves.py --merge` checks the answers against the lists and writes `tags.yaml`. A batch
    without an answers file is "waiting", not an error, so merging after each wave is safe. An
    answers file is renamed once merged, so it is never counted twice, and each merge adds a line
    to `merged.jsonl` for a later review of batch sizes.
  - If an agent hits a usage or rate limit, the session starts no more agents; what finished is
    merged and the rest waits.

`shared/scripts/claude.py` (key loading, the API call, the `claude -p` call) was removed. The
quote check it also held moved to `shared/scripts/quote.py`.
