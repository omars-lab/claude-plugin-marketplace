# Page comments: the check read only the first 8 KB of the plugin list

## What went wrong

`enable.mjs --check` asks Claude Code whether the plugin is installed and on, with
`claude plugin list --json`. On a machine with many plugins installed, the check said the plugin
was not installed when it was.

The list was read through a pipe. `claude` wrote its JSON and exited before the pipe was
drained, so the reader got only the first 8,192 bytes. The JSON was cut off mid-way, did not
parse, and the plugin looked missing. A machine with few plugins never showed it, because the
whole list fit in one pipe buffer.

## What changed

The list now goes to a temporary file instead of a pipe (`pluginVisible` in `enable.mjs`). A
file holds everything `claude` wrote, however early it exits. The test
"check reads a long plugin list in full, even from a claude that exits before its output drains"
uses a fake `claude` that writes a long list and exits at once, so the cut-off cannot come back
without the test failing.
