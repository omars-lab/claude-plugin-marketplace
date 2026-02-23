---
name: extract-urls
description: Extract URLs from screenshots — especially browser screenshots where the address bar or in-page links are visible
---

# Extract URLs from Screenshots

You are a URL extraction tool. When invoked, you run macOS Vision OCR on one or more screenshots and pull out every URL found — giving special attention to the browser address bar, which is the most common reason to screenshot a browser window.

Works on a single file, an entire directory, or the active Screenshots folder.

## What This Skill Does

1. Confirm the target (file, directory, or Screenshots folder)
2. Ensure `screenshot-ocr` conda env is ready
3. Run OCR + URL extraction on each image
4. Present a clean, deduplicated URL list — address bar URL highlighted per screenshot
5. Offer to copy URLs to clipboard or save to a file

## Task Management (MANDATORY)

**Before doing any work, create all 4 tasks:**

```javascript
TaskCreate({
  subject: "Confirm target and run extraction",
  description: "Ask user what to scan (single file, directory, or Screenshots folder). Run OCR env check. Run extract_urls.py on the target.",
  activeForm: "Extracting URLs"
})

TaskCreate({
  subject: "Present URL results",
  description: "Show results grouped by file. Highlight address bar URLs. Flag duplicates across files (same URL in multiple screenshots).",
  activeForm: "Presenting results"
})

TaskCreate({
  subject: "Handle output",
  description: "Offer to copy URLs to clipboard, save to a text/JSON file, or open selected URLs. Execute what the user requests.",
  activeForm: "Handling output"
})
```

**Dependencies:**
```javascript
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
```

## Workflow

### Step 1: Confirm Target

Use `AskUserQuestion`:
- header: "What to scan"
- question: "What should I extract URLs from?"
- options:
  - "A specific file (I'll provide the path)"
  - "A directory of screenshots"
  - "The Screenshots folder (`~/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots`)"

If a directory is chosen, ask whether to recurse into subdirectories.

### Step 2: OCR Environment Check

```bash
conda env list | grep -q screenshot-ocr && echo "exists" || echo "missing"

# If missing:
conda create -n screenshot-ocr python=3.11 -y
conda run -n screenshot-ocr pip install pyobjc-framework-Vision

# Smoke test:
conda run -n screenshot-ocr python3 -c "import Vision; print('Vision OK')"
```

### Step 3 (Task 1): Run Extraction

Locate the script:
```bash
SCRIPTS=$(find "$HOME/.claude/plugins/cache" -path "*/screenshot-manager/*/skills/extract-urls/scripts" -type d | head -1)
```

**Single file:**
```bash
conda run -n screenshot-ocr python3 "$SCRIPTS/extract_urls.py" \
  --file "/path/to/Screenshot 2026-02-18 at 10.39.02 AM.png"
```

**Directory (non-recursive):**
```bash
conda run -n screenshot-ocr python3 "$SCRIPTS/extract_urls.py" \
  --dir "/Users/$USER/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots/Claude Usage"
```

**Directory (recursive — all subdirs):**
```bash
conda run -n screenshot-ocr python3 "$SCRIPTS/extract_urls.py" \
  --dir "/Users/$USER/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots" \
  --recursive
```

**Output format:**
```json
{
  "/path/to/Screenshot 2026-02-18 at 10.39.02 AM.png": {
    "address_bar": "https://democrmfzu139843.service-now.com/now/nav/ui/classic/...",
    "urls": [
      "https://democrmfzu139843.service-now.com/now/nav/ui/classic/...",
      "https://cdnjs.cloudflare.com/ajax/libs/...",
      "https://claudeusercontent.com"
    ],
    "error": null
  }
}
```

Mark Task 1 as completed.

### Step 4 (Task 2): Present Results

Mark Task 2 as in_progress.

For each screenshot, show:

```
📸 Screenshot 2026-02-18 at 10.39.02 AM.png
   🌐 Address bar: https://democrmfzu139843.service-now.com/now/nav/ui/classic/...
   + https://cdnjs.cloudflare.com/ajax/libs/...
   + https://claudeusercontent.com

📸 Screenshot 2026-02-19 at 10.54.52 AM.png
   🌐 Address bar: https://claude.ai/settings/billing
```

**Skip files with no URLs** (OCR found no URL-shaped text) — just note the count at the end.

**Highlight cross-file duplicates** — if the same URL appears in 3+ screenshots, flag it:
```
🔁 Repeated URL (4 screenshots): https://democrmfzu139843.service-now.com/...
```

Report totals: N screenshots scanned, M unique URLs found, K with no URLs.

Mark Task 2 as completed.

### Step 5 (Task 3): Handle Output

Mark Task 3 as in_progress.

Use `AskUserQuestion`:
- header: "What to do with URLs"
- question: "What would you like to do with the extracted URLs?"
- multiSelect: true
- options:
  - "Copy all unique URLs to clipboard"
  - "Save to a text file (one URL per line)"
  - "Save to JSON (full output with per-file breakdown)"
  - "Nothing — just showing was enough"

**Copy to clipboard:**
```bash
echo "https://url1
https://url2
..." | pbcopy
echo "Copied N URLs to clipboard"
```

**Save to text file:**
```bash
# Default: next to the scanned directory, or ~/Desktop if a single file
cat > /path/to/extracted-urls.txt <<'EOF'
https://url1
https://url2
EOF
```

**Save to JSON:**
```bash
# Write the full script output JSON
python3 -c "import json; ..." > /path/to/extracted-urls.json
```

Mark Task 3 as completed.

---

## URL Extraction Logic

The script uses two layers:

**1. Full URL regex** — finds every `https?://...` string in the OCR text, regardless of position. Covers in-page links, API endpoints, CDN URLs, and anything else that looks like a URL.

**2. Address bar heuristic** — identifies which URL is most likely the browser address bar:
- Prefers URLs that appear **alone on a line** in the OCR stream (address bar text is usually isolated)
- Among those, picks the **longest** (full URL vs a link label)
- Falls back to the longest URL overall if no solo-line URL exists

**U+202F handling** — macOS screenshot filenames use a narrow no-break space before AM/PM. The script resolves paths transparently, so passing a filename with a regular space works fine.

---

## Tips

- **Browser screenshots** — `address_bar` will almost always be populated and accurate. The address bar appears as a single line of text in the OCR stream.
- **Non-browser screenshots** — `address_bar` may be null or point to a URL that appeared in the content body. All found URLs are still listed in `urls`.
- **Dense screenshots** (lots of UI text) — OCR may pick up partial URLs or mis-read characters. Review with the original screenshot if a URL looks garbled.
- **Terminals / code editors** — URLs in code or terminal output are extracted too, not just browser address bars.

---

## Related Skills

- **suggest-groupings** — uses OCR content (including URLs) to find misplaced screenshots
- **sort-dirs** — prefix directories with dates after organising
- **introduce** — overview of all skills
