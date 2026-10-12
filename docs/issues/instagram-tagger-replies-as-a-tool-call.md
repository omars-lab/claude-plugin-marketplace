# The Instagram tagger gets its answer through a tool call, not as JSON text

**Where:** `plugins/instagram-manager/skills/tag-saves/scripts/tag_saves.py`, and `call_tool` in
`plugins/instagram-manager/shared/scripts/claude.py`.

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
