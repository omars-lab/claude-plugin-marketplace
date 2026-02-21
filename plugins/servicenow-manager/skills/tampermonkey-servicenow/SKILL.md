---
name: tampermonkey-servicenow
description: ServiceNow-specific Tampermonkey userscript guidance with real-world examples and ServiceNow-specific patterns
---

# Tampermonkey: ServiceNow Scripts

You are a ServiceNow Tampermonkey specialist. When invoked, provide ServiceNow-specific guidance for building Tampermonkey userscripts, including reference patterns from production ServiceNow scripts.

## What This Skill Does

This skill:
1. Provides ServiceNow-specific Tampermonkey metadata patterns
2. Covers ServiceNow DOM selectors and API access patterns
3. References real-world ServiceNow script structures
4. Covers ServiceNow-specific gotchas (iframe navigation, GlideAjax, etc.)

## Real-World Reference Scripts

These production scripts demonstrate proven patterns for ServiceNow automation:

### servicenow-transcript-extractor (v2.1.2)

**Purpose:** Extract training transcripts from ServiceNow learning portal
**Key patterns:**
- `@match` targeting ServiceNow `*.service-now.com` domains
- Waiting for ServiceNow's Angular/React app to finish loading before DOM access
- Using `window.g_user` to access ServiceNow session context
- Handling ServiceNow's iframe-within-iframe navigation model

**Metadata pattern:**
```javascript
// ==UserScript==
// @name         ServiceNow Transcript Extractor
// @namespace    https://github.com/yourusername
// @version      2.1.2
// @description  Extract training transcript from ServiceNow portal
// @author       Your Name
// @match        https://*.service-now.com/learning*
// @match        https://*.service-now.com/lp*
// @grant        GM_setClipboard
// @grant        GM_notification
// @grant        unsafeWindow
// ==/UserScript==
```

### servicenow-lab-downloader (v1.0.17)

**Purpose:** Download lab PDFs/materials from ServiceNow learning
**Key patterns:**
- `@require` for utility libraries (lodash, moment)
- `GM_xmlhttpRequest` for cross-origin requests to ServiceNow REST API
- `GM_getValue`/`GM_setValue` for persisting state across page loads
- Handling CSRF tokens in ServiceNow API calls

**Metadata pattern:**
```javascript
// ==UserScript==
// @name         ServiceNow Lab Downloader
// @namespace    https://github.com/yourusername
// @version      1.0.17
// @description  Download lab materials from ServiceNow training
// @author       Your Name
// @match        https://*.service-now.com/now/nav/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_download
// @connect      *.service-now.com
// ==/UserScript==
```

## ServiceNow-Specific Patterns

### Waiting for ServiceNow App Initialization

ServiceNow loads asynchronously. Always wait before accessing the DOM:

```javascript
function waitForServiceNow(callback, maxAttempts = 30) {
  let attempts = 0;
  const check = setInterval(() => {
    attempts++;
    // Check that the ServiceNow app has initialized
    if (document.querySelector('.navpage-main') || window.NOW) {
      clearInterval(check);
      callback();
    } else if (attempts >= maxAttempts) {
      clearInterval(check);
      console.error('[Script] ServiceNow app did not load in time');
    }
  }, 500);
}

waitForServiceNow(() => {
  // Your script logic here
});
```

### Accessing ServiceNow User Context

```javascript
// Current user info (available after app init)
const user = window.g_user || {};
const userId = user.userID;
const userName = user.userName;
const fullName = user.getFullName();
```

### ServiceNow REST API via GM_xmlhttpRequest

```javascript
GM_xmlhttpRequest({
  method: 'GET',
  url: `${window.location.origin}/api/now/table/sys_user?sysparm_query=user_name=${encodeURIComponent(userId)}`,
  headers: {
    'Accept': 'application/json',
    'X-UserToken': window.g_ck  // CSRF token
  },
  onload: (response) => {
    const data = JSON.parse(response.responseText);
    // handle data
  }
});
```

### ServiceNow GlideAjax (When Running Inside ServiceNow)

```javascript
// Only works in ServiceNow context, not cross-origin
const ga = new GlideAjax('YourScriptInclude');
ga.addParam('sysparm_name', 'yourMethod');
ga.addParam('sysparm_value', 'yourParam');
ga.getXML((response) => {
  const answer = response.responseXML.documentElement.getAttribute('answer');
});
```

### Handling ServiceNow Iframes

ServiceNow often loads content in iframes. To access iframe content:

```javascript
function getServiceNowFrame() {
  // ServiceNow main content iframe
  return document.querySelector('#gsft_main') ||
         document.querySelector('iframe[name="gsft_main"]');
}

const frame = getServiceNowFrame();
if (frame && frame.contentDocument) {
  const innerDoc = frame.contentDocument;
  // Access DOM inside iframe
  const field = innerDoc.querySelector('#your_field_id');
}
```

### URL Patterns for @match

Common ServiceNow URL patterns:

```javascript
// @match        https://*.service-now.com/*
// @match        https://*.service-now.com/nav_to.do*
// @match        https://*.service-now.com/now/nav/*
// @match        https://*.service-now.com/$pwd_reset.do*
// @match        https://developer.servicenow.com/*
```

## Integration with script-manager

This skill provides ServiceNow context. Use it together with `script-manager:tampermonkey-create` for the full workflow:

1. `/servicenow-manager:tampermonkey-servicenow` — Get ServiceNow patterns and context
2. `/script-manager:tampermonkey-create` — Follow the full script creation workflow

## Task Management

```javascript
TaskCreate({
  subject: "Gather ServiceNow script requirements",
  description: "What does the script automate? Which ServiceNow URL? What permissions needed?",
  activeForm: "Gathering requirements"
})

TaskCreate({
  subject: "Apply ServiceNow-specific patterns",
  description: "Select appropriate @match patterns, API access, iframe handling",
  activeForm: "Applying ServiceNow patterns"
})
```

## AskUserQuestion

When invoked, ask:

- What ServiceNow workflow does the script automate?
- Which ServiceNow instance/URL pattern to target?
- Does it need cross-origin requests (GM_xmlhttpRequest)?
- Does it need to access iframes?

## Related Skills

- **script-manager:tampermonkey-create** — Full Tampermonkey script creation workflow
- **servicenow-manager:introduce** — Overview of this plugin
