# Script Manager Plugin

Create and manage Tampermonkey userscripts with production-ready best practices learned from real-world implementations.

## Features

- ✅ **Complete metadata** - All required @directives
- ✅ **Version management** - Auto-syncing const VERSION
- ✅ **Robust waiting** - MutationObserver patterns for element and content loading
- ✅ **Iframe handling** - Detect and wait for iframe content
- ✅ **Error handling** - Try-catch with persistent logging
- ✅ **Event management** - Proper preventDefault/stopPropagation
- ✅ **Visual feedback** - Status messages and hover effects
- ✅ **Click isolation** - Target verification to prevent accidental clicks
- ✅ **Debug logging** - localStorage-based persistent logs
- ✅ **Publishing workflow** - Makefile + publisher script setup

## Skills

### `/tampermonkey-create`

Creates a production-ready Tampermonkey userscript with all best practices:

**Usage:**
```
/tampermonkey-create
```

**What it creates:**
1. Userscript file with complete metadata
2. Makefile for publishing to GitHub Gist
3. Publisher script (reusable)
4. Documentation
5. Git ignore configuration

**Prompts you for:**
- Script name
- Description
- Target URL pattern (@match)
- What the script should do
- Where buttons/UI should be added

## Best Practices Included

### 1. Metadata Requirements
- @name, @namespace, @version
- @description, @author
- @match patterns
- @updateURL, @downloadURL (auto-injected)
- @grant permissions
- @icon

### 2. Version Management
```javascript
// @version 1.0.0
const VERSION = '1.0.0'; // Auto-synced by Makefile
console.log(`🚀 Script Version: ${VERSION}`);
```

### 3. Element Waiting
```javascript
function waitForElement(selector, timeout = 30000) {
    // MutationObserver pattern
    // Waits for element to appear in DOM
}
```

### 4. Content Waiting
```javascript
function waitForContent(element, timeout = 30000) {
    // Don't just wait for container!
    // Wait for actual content (li, p elements)
}
```

### 5. Iframe Handling
```javascript
// Detect iframe content
const iframe = element.querySelector('iframe');
if (iframe) {
    // Wait for iframe.onload
    // Access iframe.contentDocument
    // Switch to iframe body as content source
}
```

### 6. Error Handling
```javascript
// Persistent logging (survives redirects)
function persistentLog(message, level) {
    console.log(message);
    localStorage.setItem(LOG_KEY, ...);
}

// Visual status messages
function showStatus(message, type) {
    // Show in top-right corner
}
```

### 7. Event Handling
```javascript
button.addEventListener('click', async function(e) {
    // Verify click target
    if (!button.contains(e.target)) return false;

    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    // Your code here
}, true); // Use capture phase
```

### 8. Button Styling
```javascript
// Custom styling (avoid className inheritance)
button.style.cssText = `
    background: rgba(33, 150, 243, 0.1);
    border: 2px solid transparent;
    padding: 12px;
    min-width: 45px;
    min-height: 45px;
    z-index: 1000;
`;

// Hover feedback
button.addEventListener('mouseenter', () => {
    button.style.background = 'rgba(33, 150, 243, 0.2)';
    button.style.transform = 'scale(1.05)';
});
```

### 9. Publishing Workflow
```bash
make validate  # Check metadata
make publish   # Auto-increment version, publish to gist
make url       # Get install URL
```

## Real-World Examples

This plugin is based on production scripts:

1. **ServiceNow Transcript Extractor** (v2.1.2)
   - Waits for transcript container AND content
   - Extracts breadcrumb navigation
   - Generates smart filenames
   - Markdown formatting

2. **ServiceNow Lab Downloader** (v1.0.17)
   - Handles iframe content
   - HTML to Markdown conversion
   - Persistent logging across redirects
   - Visual feedback
   - Click target verification

## Prerequisites

- Tampermonkey browser extension
- Developer Mode enabled (Chrome/Edge 138+)
- GitHub CLI (`gh`) for publishing
- `make` for automation

## Installation

This plugin is part of the oeid-claude-plugin-marketplace.

## License

MIT

## Author

Omar Eid (with Claude Code assistance)

## Version

1.0.0 - Initial release with comprehensive Tampermonkey best practices
