# Batch Execution Feature - Complete Documentation

## 📋 Table of Contents
1. [Overview](#overview)
2. [What is Batch Execution?](#what-is-batch-execution)
3. [Architecture](#architecture)
4. [Implementation Journey](#implementation-journey)
5. [Problems Faced & Solutions](#problems-faced--solutions)
6. [Code Walkthrough](#code-walkthrough)
7. [Usage Guide](#usage-guide)
8. [Edge Cases Handled](#edge-cases-handled)

---

## Overview

**Batch Execution** is a feature that allows users to scrape multiple pages/resources by providing a list of identifiers. Instead of manually running the scraper for each URL, you can:
- Provide a URL template with a placeholder (e.g., `https://example.com/item/{id}`)
- Provide a list of identifiers (e.g., `item1, item2, item3`)
- The system automatically loops through each identifier, fetches the data, and combines all results into a single CSV export.

---

## What is Batch Execution?

### The Problem It Solves

Imagine you want to scrape 100 product pages from an e-commerce site. Without batch execution:
- You would need to run the scraper 100 times manually
- Each run would create a separate CSV file
- You'd have to manually combine all the results

### The Solution

With batch execution:
1. You provide a **URL template**: `https://shop.com/product/{id}`
2. You provide a **list of product IDs**: `P001, P002, P003, ..., P100`
3. The system automatically:
   - Replaces `{id}` with each identifier
   - Fetches each page
   - Extracts data from each page
   - Combines all records into ONE CSV file

### Simple Analogy

Think of it like a mail merge in Microsoft Word:
- You have a template letter with `{name}` placeholder
- You have a list of names
- The system creates personalized letters for each name

Batch execution does the same, but for web scraping!

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Batch Identifiers Input:  "item1, item2, item3"        │   │
│  │  Variable Name:            "id"                          │   │
│  │  URL Template:             "https://example.com/{id}"    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                    splits by comma/newline                      │
│                              │                                   │
│                              ▼                                   │
│              ["item1", "item2", "item3"]                        │
└─────────────────────────────────────────────────────────────────┘
                               │
                    HTTP POST /analyze/document
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FOR EACH identifier IN batch_identifiers:              │   │
│  │      1. Replace {id} in URL with identifier             │   │
│  │      2. Fetch the page                                   │   │
│  │      3. Extract records                                  │   │
│  │      4. Add to all_records                               │   │
│  │      5. Wait delay_ms before next iteration              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│              Combined CSV with ALL records                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Journey

### Phase 1: Initial Feature Addition

**Goal**: Add batch execution support to XHR and Selenium modes.

**Files Modified**:
- `backend/app/schemas/requests.py` - Added schema fields
- `backend/app/api/analyze.py` - Added batch loop logic
- `frontend/src/App.tsx` - Added UI controls

**Initial Implementation** (XHR/Selenium only):
```python
# In XhrAnalyzeRequest schema
batch_identifiers: Optional[list[str]] = Field(default=None)
batch_variable_name: str = Field(default="id")
```

### Phase 2: Extending to Document Mode

**Problem**: Document mode didn't have batch execution support.

**Solution**: Added the same fields to `DocumentAnalyzeRequest` and implemented the batch loop in `analyze_document()`.

---

## Problems Faced & Solutions

### 🐛 Problem 1: URL Placeholder Not Being Replaced

**Symptom**: 
The backend was fetching URLs like:
```
https://codeforces.com/problemset/problem/%7Bid%7D
```
Instead of:
```
https://codeforces.com/problemset/problem/2182/A
```

**Root Cause**: 
The `{id}` placeholder was being URL-encoded by the HTTP library before the string replacement happened.

**Explanation for Beginners**:
- In URLs, special characters like `{` and `}` get converted to `%7B` and `%7D`
- This is called "URL encoding" or "percent encoding"
- The problem was: we were sending `{id}` to the HTTP library, which encoded it BEFORE we replaced it

**Solution**:
Perform the string replacement BEFORE passing the URL to the HTTP fetch function:

```python
# WRONG (what we had before):
# The URL goes to HTTP library with {id} still in it
fetch = get_bytes(payload.url, ...)  # {id} gets encoded to %7Bid%7D

# CORRECT (what we fixed):
# Replace {id} first, then fetch
target = f"{{{payload.batch_variable_name}}}"  # Creates "{id}"
curr_url = curr_url.replace(target, str(identifier))  # Replace {id} with actual value
fetch = get_bytes(curr_url, ...)  # URL is clean
```

**Key Learning**: 
Always perform string template substitution BEFORE the string enters any library that might transform it.

---

### 🐛 Problem 2: Backend Not Receiving Batch Identifiers

**Symptom**: 
The decision trace showed `batch_identifiers_count: 0` even when the user entered identifiers.

**Root Cause**:
Multiple issues:
1. Frontend was using only comma (`,`) to split, but user's list had newlines
2. Complex ternary logic was sometimes returning `null` incorrectly

**Solution**:
```typescript
// BEFORE (fragile):
batch_identifiers: docBatchIds.split(',').map(s => s.trim()).filter(Boolean).length > 0 
  ? docBatchIds.split(',').map(s => s.trim()).filter(Boolean) 
  : null

// AFTER (robust):
batch_identifiers: docBatchIds.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
```

**Explanation**:
- `/[\n,]+/` is a regex that matches one or more newlines OR commas
- This handles: `item1, item2, item3` AND `item1\nitem2\nitem3`
- `.filter(Boolean)` removes empty strings
- No more complex ternary - just returns the array (empty array if no input)

---

### 🐛 Problem 3: Backend Not Reloading Code Changes

**Symptom**: 
Code changes were made but the backend kept using old code.

**Root Cause**:
The Uvicorn server had been running for 3+ hours without the `--reload` flag, so it didn't pick up file changes.

**Solution**:
Restart the backend with `--reload` flag:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Key Learning**:
During development, always use `--reload` so the server automatically restarts when files change.

---

### 🐛 Problem 4: HTTP 500 Error from Frontend

**Symptom**:
Frontend showed "HTTP 500 Internal Server Error" when trying to scrape.

**Root Cause**:
The Vite dev server proxy was configured to forward requests to port 8001, but the backend was running on port 8000.

**The Mismatch**:
```typescript
// vite.config.ts (WRONG)
proxy: {
  '/analyze': 'http://127.0.0.1:8001',  // Port 8001
  '/download': 'http://127.0.0.1:8001', // Port 8001
}

// Backend running on:
uvicorn app.main:app --port 8000  // Port 8000!
```

**Solution**:
```typescript
// vite.config.ts (CORRECT)
proxy: {
  '/analyze': 'http://127.0.0.1:8000',
  '/download': 'http://127.0.0.1:8000',
}
```

**Explanation for Beginners**:
- The frontend (React) runs on port 5173
- The backend (FastAPI) runs on port 8000
- When frontend makes API calls, Vite's proxy forwards them to the backend
- If the proxy points to wrong port, requests fail with 500 error

---

### 🐛 Problem 5: 403 Forbidden from Target Website

**Symptom**:
After fixing all code issues, Codeforces returned 403 Forbidden.

**Root Cause**:
This is NOT a code bug. Codeforces has anti-bot protection that blocks:
- Simple User-Agent strings
- Requests without browser cookies
- Requests without JavaScript execution

**Solution**:
Use **Selenium mode** for websites with anti-bot protection. Selenium uses a real browser (Chrome) which:
- Has realistic headers
- Executes JavaScript
- Handles cookies naturally
- Appears as a real user

**Key Learning**:
Some websites require browser automation. Document/XHR modes are faster but may be blocked.

---

## Code Walkthrough

### Backend: Schema Definition

**File**: `backend/app/schemas/requests.py`

```python
class DocumentAnalyzeRequest(BaseModel):
    url: str = Field(min_length=1)
    # ... other fields ...
    
    # Batch execution fields
    batch_identifiers: Optional[list[str]] = Field(
        default=None, 
        description="List of identifiers to loop over"
    )
    batch_variable_name: str = Field(
        default="id", 
        description="Variable name to replace with identifier"
    )
```

**What This Does**:
- `batch_identifiers`: Optional list of strings. If provided, we loop over them.
- `batch_variable_name`: The placeholder name (default "id"). We look for `{id}` in the URL.

---

### Backend: Batch Loop Logic

**File**: `backend/app/api/analyze.py`

```python
@router.post("/document", response_model=AnalyzeResponse)
def analyze_document(payload: DocumentAnalyzeRequest) -> AnalyzeResponse:
    trace: list[DecisionTraceEntry] = []
    
    # Debug: Log how many identifiers we received
    trace.append(_trace("debug_config", ok=True, details={
        "batch_identifiers_count": len(payload.batch_identifiers) if payload.batch_identifiers else 0,
        "batch_var": payload.batch_variable_name
    }))

    def execute_pass(url: str) -> list[dict[str, Any]]:
        """Fetch one URL and extract records from it."""
        # 1. Fetch the HTML
        fetch = get_bytes(url, headers=payload.headers, cookies=payload.cookies)
        
        if fetch.status_code >= 400:
            return []  # Failed, return empty
        
        # 2. Extract records from HTML
        html = fetch.content.decode("utf-8", errors="replace")
        records = extract_records_from_html(html, css_selector=payload.css_selector)
        
        return records

    # Main batch loop
    all_records: list[dict[str, Any]] = []
    
    # If no batch identifiers, use [None] so we run once with original URL
    identifiers = payload.batch_identifiers if payload.batch_identifiers else [None]

    for idx, identifier in enumerate(identifiers):
        curr_url = payload.url
        
        if identifier is not None:
            # CRITICAL: Replace {id} with actual identifier BEFORE fetching
            target = f"{{{payload.batch_variable_name}}}"  # Creates "{id}"
            curr_url = curr_url.replace(target, str(identifier))
            
            trace.append(_trace("batch_iteration", ok=True, details={
                "identifier": identifier,
                "url": curr_url
            }))
        
        try:
            pass_records = execute_pass(curr_url)
            all_records.extend(pass_records)  # Add to combined list
        except Exception as e:
            trace.append(_trace("batch_error", ok=False, details={
                "identifier": identifier,
                "error": str(e)
            }))
        
        # Delay between iterations (be polite to servers)
        if payload.delay_ms > 0 and idx < len(identifiers) - 1:
            time.sleep(payload.delay_ms / 1000.0)

    # ... rest of the function handles filtering and CSV export ...
```

**Step-by-Step Explanation**:

1. **Prepare the identifier list**: If user provided batch IDs, use them. Otherwise, use `[None]` (run once).

2. **Loop through identifiers**: For each identifier:
   - Start with the original URL template
   - Replace `{id}` with the actual identifier value
   - Fetch the page
   - Extract records
   - Add records to the combined list
   - Wait before next request (politeness delay)

3. **Error handling**: If one identifier fails, we log it and continue with others.

4. **Combine results**: All records from all pages go into one `all_records` list.

---

### Frontend: UI Components

**File**: `frontend/src/App.tsx`

```tsx
// State for batch execution
const [docBatchIds, setDocBatchIds] = useState('')
const [docBatchVar, setDocBatchVar] = useState('id')

// In the form JSX
<h3>Batch Execution</h3>
<div className="row rowWrap">
  <label className="field grow">
    <div className="label">Batch Identifiers (comma-separated)</div>
    <textarea
      value={docBatchIds}
      onChange={(e) => setDocBatchIds(e.target.value)}
      rows={2}
      placeholder="e.g. item1, item2, item3"
    />
    <div className="hint">Leave empty for single execution. Variables: {'{id}'} in URL.</div>
  </label>
</div>

{docBatchIds.trim() && (
  <div className="row rowWrap">
    <label className="field">
      <div className="label">Variable Name</div>
      <input value={docBatchVar} onChange={(e) => setDocBatchVar(e.target.value)} />
    </label>
    <label className="field">
      <div className="label">Delay (ms)</div>
      <input type="number" value={xhrDelayMs} onChange={(e) => setXhrDelayMs(Number(e.target.value))} />
    </label>
  </div>
)}
```

**Explanation**:
- Text area for entering identifiers (comma or newline separated)
- Variable name input (defaults to "id")
- Delay input for politeness between requests
- The variable name input only shows if identifiers are provided

---

### Frontend: Building the API Payload

```typescript
payload = {
  url,
  requested_fields: parsedRequestedFields,
  headers: headersParsed.value,
  css_selector: docCssSelector.trim() || null,
  pagination,
  delay_ms: xhrDelayMs,
  // Split by comma OR newline, trim whitespace, remove empty strings
  batch_identifiers: docBatchIds.split(/[\n,]+/).map(s => s.trim()).filter(Boolean),
  batch_variable_name: docBatchVar,
}
```

**The Splitting Logic Explained**:
```javascript
"item1, item2, item3"
  .split(/[\n,]+/)     // Split by comma or newline → ["item1", " item2", " item3"]
  .map(s => s.trim())  // Remove whitespace → ["item1", "item2", "item3"]
  .filter(Boolean)     // Remove empty strings → ["item1", "item2", "item3"]
```

---

## Usage Guide

### Step 1: Enter URL Template

Enter a URL with a placeholder:
```
https://example.com/product/{id}
```

The `{id}` will be replaced with each identifier.

### Step 2: Enter Batch Identifiers

Enter your identifiers, separated by commas or newlines:
```
P001, P002, P003, P004, P005
```

Or:
```
P001
P002
P003
P004
P005
```

### Step 3: Set Variable Name (Optional)

Default is `id`. Change if your URL uses different placeholder:
- URL: `https://example.com/user/{username}/profile`
- Variable Name: `username`
- Identifiers: `john, jane, bob`

### Step 4: Set Delay

Recommended: 500ms or more. This prevents overwhelming the target server and reduces chance of being blocked.

### Step 5: Run Extraction

Click "Extract Data". The system will:
1. Process each identifier
2. Show progress in decision trace
3. Combine all results into one CSV

---

## Edge Cases Handled

| Scenario | Behavior |
|----------|----------|
| Empty batch identifiers | Single execution with original URL |
| Missing `{id}` in URL | URL fetched as-is for each identifier |
| Invalid identifier (404/403) | Logged as error, continues with remaining |
| Identifier with special chars (`/`) | Direct replacement (no encoding) |
| Partial batch success | Exports successful records only |
| Rate limiting | Configurable delay between requests |

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `backend/app/schemas/requests.py` | Added `batch_identifiers` and `batch_variable_name` to Document, XHR, Selenium schemas |
| `backend/app/api/analyze.py` | Added batch loop logic to all three analyze endpoints |
| `frontend/src/App.tsx` | Added UI controls for batch execution in all three modes |
| `frontend/vite.config.ts` | Fixed proxy port (8001 → 8000) |

---

## Lessons Learned

1. **String replacement must happen before URL encoding** - Libraries may transform strings in unexpected ways.

2. **Test with debug logging** - Adding trace entries helped identify exactly where the problem was.

3. **Check infrastructure** - Port mismatches and server reload issues can look like code bugs.

4. **Handle edge cases gracefully** - Empty lists, failed requests, and special characters should all work.

5. **Anti-bot protection is real** - Some sites require Selenium for browser automation.

---

## Future Improvements

1. **Progress indicator**: Show real-time progress (e.g., "Processing 5/100...")
2. **Retry failed identifiers**: Option to retry failed items
3. **Resume capability**: Save state to resume interrupted batch jobs
4. **Parallel execution**: Process multiple identifiers simultaneously (with rate limiting)
5. **Identifier from file**: Upload CSV of identifiers instead of pasting

---

*Documentation created: 2026-01-05*
*Feature: Batch Execution for Web Data Scraping Assistant*
