import './App.css'

import { useMemo, useState } from 'react'

const backendBase = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/$/, '')

function withBackendBase(path: string): string {
  if (!path) return path
  if (/^https?:\/\//i.test(path)) return path

  // Default: use same-origin relative paths (Vite proxy in dev)
  if (!backendBase) return path

  if (path.startsWith('/')) return `${backendBase}${path}`
  return `${backendBase}/${path}`
}

type DecisionTraceEntry = {
  step: string
  ok: boolean
  ms?: number | null
  details?: Record<string, unknown> | null
}

type AnalyzeResponse = {
  mode_used: 'document' | 'xhr' | 'selenium'
  has_data: boolean
  message: string
  csv_url: string | null
  record_count: number
  decision_trace: DecisionTraceEntry[]
}

type Pagination =
  | { type: 'page_param'; param: string; start: number; end: number }
  | {
    type: 'offset'
    offset_param: string
    limit_param: string
    limit: number
    max_pages: number
    start_offset: number
  }
  | {
    type: 'cursor'
    cursor_param: string
    cursor_field: string
    max_pages: number
    initial_cursor: string | null
  }

type Mode = 'document' | 'xhr' | 'selenium'

function parseJsonObject(text: string): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  const trimmed = text.trim()
  if (!trimmed) return { ok: true, value: {} }

  try {
    const parsed = JSON.parse(trimmed)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { ok: false, error: 'Must be a JSON object (e.g. {"User-Agent":"..."}).' }
    }
    return { ok: true, value: parsed as Record<string, unknown> }
  } catch (e) {
    return { ok: false, error: `Invalid JSON: ${(e as Error).message}` }
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(withBackendBase(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status} ${res.statusText}${text ? `: ${text}` : ''}`)
  }

  return (await res.json()) as T
}

function App() {
  const [mode, setMode] = useState<Mode>('document')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)

  // Shared
  const [url, setUrl] = useState('')
  const [requestedFields, setRequestedFields] = useState('')
  const [headersJson, setHeadersJson] = useState('{"User-Agent":"Mozilla/5.0"}')

  // Document mode
  const [docCssSelector, setDocCssSelector] = useState('')
  // Document pagination (page_param only)
  const [docUsePagination, setDocUsePagination] = useState(true)
  const [docPageParam, setDocPageParam] = useState('page')
  const [docStart, setDocStart] = useState(1)
  const [docEnd, setDocEnd] = useState(5)
  const [docBatchIds, setDocBatchIds] = useState('')
  const [docBatchVar, setDocBatchVar] = useState('id')

  // XHR
  const [apiUrl, setApiUrl] = useState('')
  const [xhrMethod, setXhrMethod] = useState<'GET' | 'POST'>('GET')
  const [paramsJson, setParamsJson] = useState('{}')
  const [bodyJson, setBodyJson] = useState('')  // Request body for POST
  const [cookiesJson, setCookiesJson] = useState('{}')  // Cookies for authenticated requests
  const [xhrDelayMs, setXhrDelayMs] = useState(500)
  const [xhrMaxRetries, setXhrMaxRetries] = useState(2)
  const [xhrPaginationType, setXhrPaginationType] = useState<'none' | Pagination['type']>('none')
  const [xhrPageParam, setXhrPageParam] = useState('page')
  const [xhrStart, setXhrStart] = useState(1)
  const [xhrEnd, setXhrEnd] = useState(5)
  const [xhrOffsetParam, setXhrOffsetParam] = useState('_start')
  const [xhrLimitParam, setXhrLimitParam] = useState('_limit')
  const [xhrLimit, setXhrLimit] = useState(10)
  const [xhrMaxPages, setXhrMaxPages] = useState(3)
  const [xhrStartOffset, setXhrStartOffset] = useState(0)
  const [xhrCursorParam, setXhrCursorParam] = useState('cursor')
  const [xhrCursorField, setXhrCursorField] = useState('meta.next_cursor')
  const [xhrInitialCursor, setXhrInitialCursor] = useState('*')
  const [xhrCursorMaxPages, setXhrCursorMaxPages] = useState(3)
  const [xhrBatchIds, setXhrBatchIds] = useState('')
  const [xhrBatchVar, setXhrBatchVar] = useState('id')

  // Selenium
  const [seleniumEnabled, setSeleniumEnabled] = useState(false)
  const [cssSelector, setCssSelector] = useState('')
  const [waitTime, setWaitTime] = useState(10)
  const [selUsePagination, setSelUsePagination] = useState(false)
  const [selPageParam, setSelPageParam] = useState('page')
  const [selStart, setSelStart] = useState(1)
  const [selEnd, setSelEnd] = useState(5)
  const [selScrollCount, setSelScrollCount] = useState(0)
  const [selScrollDelay, setSelScrollDelay] = useState(2000)
  const [selBatchIds, setSelBatchIds] = useState('')
  const [selBatchVar, setSelBatchVar] = useState('id')

  const parsedRequestedFields = useMemo(
    () =>
      requestedFields
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    [requestedFields],
  )

  const headersParsed = useMemo(() => parseJsonObject(headersJson), [headersJson])
  const paramsParsed = useMemo(() => parseJsonObject(paramsJson), [paramsJson])
  const bodyParsed = useMemo(() => parseJsonObject(bodyJson), [bodyJson])
  const cookiesParsed = useMemo(() => parseJsonObject(cookiesJson), [cookiesJson])

  async function runAnalyze() {
    setError(null)
    setResult(null)

    if (!url.trim()) return setError('URL is required.')

    if (!headersParsed.ok) return setError(`Headers JSON error: ${headersParsed.error}`)
    if (!paramsParsed.ok) return setError(`Params JSON error: ${paramsParsed.error}`)

    if (mode === 'xhr' && !apiUrl.trim()) return setError('API URL is required for XHR mode.')
    if (mode === 'selenium' && !seleniumEnabled) return setError('Selenium is disabled. Enable it explicitly first.')
    if (mode === 'selenium' && !cssSelector.trim()) return setError('CSS selector is required for Selenium mode.')

    let payload: Record<string, unknown>
    let endpoint = ''

    if (mode === 'document') {
      endpoint = '/analyze/document'
      const pagination: Pagination | null = docUsePagination
        ? { type: 'page_param', param: docPageParam, start: docStart, end: docEnd }
        : null

      payload = {
        url,
        requested_fields: parsedRequestedFields,
        headers: headersParsed.value,
        css_selector: docCssSelector.trim() || null,
        pagination,
        delay_ms: xhrDelayMs,
        batch_identifiers: docBatchIds.split(/[\n,]+/).map(s => s.trim()).filter(Boolean),
        batch_variable_name: docBatchVar,
      }
    } else if (mode === 'xhr') {
      endpoint = '/analyze/xhr'
      let pagination: Pagination | null = null

      if (xhrPaginationType === 'page_param') {
        pagination = { type: 'page_param', param: xhrPageParam, start: xhrStart, end: xhrEnd }
      } else if (xhrPaginationType === 'offset') {
        pagination = {
          type: 'offset',
          offset_param: xhrOffsetParam,
          limit_param: xhrLimitParam,
          limit: xhrLimit,
          max_pages: xhrMaxPages,
          start_offset: xhrStartOffset,
        }
      } else if (xhrPaginationType === 'cursor') {
        pagination = {
          type: 'cursor',
          cursor_param: xhrCursorParam,
          cursor_field: xhrCursorField,
          max_pages: xhrCursorMaxPages,
          initial_cursor: xhrInitialCursor.trim() ? xhrInitialCursor.trim() : null,
        }
      }

      if (xhrMethod === 'POST' && !bodyParsed.ok) return setError(`Body JSON error: ${bodyParsed.error}`)
      if (!cookiesParsed.ok) return setError(`Cookies JSON error: ${cookiesParsed.error}`)

      const batchList = xhrBatchIds.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)

      payload = {
        api_url: apiUrl,
        method: xhrMethod,
        requested_fields: parsedRequestedFields,
        headers: headersParsed.ok ? headersParsed.value : {},
        params: paramsParsed.ok ? paramsParsed.value : {},
        body: xhrMethod === 'POST' && bodyParsed.ok ? bodyParsed.value : null,
        cookies: cookiesParsed.ok ? cookiesParsed.value : {},
        delay_ms: xhrDelayMs,
        max_retries: xhrMaxRetries,
        pagination,
        batch_identifiers: batchList.length > 0 ? batchList : null,
        batch_variable_name: xhrBatchVar,
      }
    } else {
      endpoint = '/analyze/selenium'
      const pagination: Pagination | null = selUsePagination
        ? { type: 'page_param', param: selPageParam, start: selStart, end: selEnd }
        : null

      if (!cookiesParsed.ok) return setError(`Cookies JSON error: ${cookiesParsed.error}`)

      const batchList = selBatchIds.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)

      payload = {
        url,
        requested_fields: parsedRequestedFields,
        css_selector: cssSelector,
        cookies: cookiesParsed.value,
        wait_time: waitTime,
        scroll_count: selScrollCount,
        scroll_delay_ms: selScrollDelay,
        pagination,
        delay_ms: xhrDelayMs, // Reusing XHR global delay for now
        batch_identifiers: batchList.length > 0 ? batchList : null,
        batch_variable_name: selBatchVar,
      }
    }

    setBusy(true)
    try {
      const res = await postJson<AnalyzeResponse>(endpoint, payload)
      setResult(res)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Web Data Scraping Assistant</h1>
        <p className="sub">
          Extract structured data from any website. Select your mode and configure the extraction parameters below.
        </p>
      </header>

      <section className="panel">
        <h2>Configuration</h2>
        <div className="row rowWrap">
          <label className="field">
            <div className="label">Scraping Mode</div>
            <div className="seg">
              <button className={mode === 'document' ? 'segBtn active' : 'segBtn'} onClick={() => setMode('document')}>
                Document
              </button>
              <button className={mode === 'xhr' ? 'segBtn active' : 'segBtn'} onClick={() => setMode('xhr')}>
                XHR / API
              </button>
              <button className={mode === 'selenium' ? 'segBtn active' : 'segBtn'} onClick={() => setMode('selenium')}>
                Selenium
              </button>
            </div>
          </label>
        </div>

        <div className="row rowWrap">
          <label className="field grow">
            <div className="label">Target URL</div>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/page" />
          </label>
        </div>

        <div className="row rowWrap">
          <label className="field grow">
            <div className="label">Headers (JSON object)</div>
            <textarea value={headersJson} onChange={(e) => setHeadersJson(e.target.value)} rows={3} />
            {!headersParsed.ok ? <div className="hint err">{headersParsed.error}</div> : <div className="hint">Used for Document/XHR fetch.</div>}
          </label>
        </div>

        {mode === 'document' && (
          <div className="subpanel">
            <h2>Document Settings</h2>
            <div className="row rowWrap">
              <label className="field grow">
                <div className="label">CSS Selector (optional)</div>
                <input
                  value={docCssSelector}
                  onChange={(e) => setDocCssSelector(e.target.value)}
                  placeholder="e.g. .product-card, .item-row, table tr"
                />
                <div className="hint">Leave empty to auto-detect tables. Provide a selector for repeated elements to extract.</div>
              </label>
            </div>
            <label className="check">
              <input type="checkbox" checked={docUsePagination} onChange={(e) => setDocUsePagination(e.target.checked)} />
              Enable pagination (page param)
            </label>
            {docUsePagination && (
              <div className="row rowWrap">
                <label className="field">
                  <div className="label">Param</div>
                  <input value={docPageParam} onChange={(e) => setDocPageParam(e.target.value)} />
                </label>
                <label className="field">
                  <div className="label">Start</div>
                  <input type="number" value={docStart} onChange={(e) => setDocStart(Number(e.target.value))} />
                </label>
                <label className="field">
                  <div className="label">End</div>
                  <input type="number" value={docEnd} onChange={(e) => setDocEnd(Number(e.target.value))} />
                </label>
              </div>
            )}

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
                  <div className="hint">Default: "id". Replaces {'{id}'} in URL.</div>
                </label>
                <label className="field">
                  <div className="label">Delay (ms)</div>
                  <input
                    type="number"
                    value={xhrDelayMs}
                    onChange={(e) => setXhrDelayMs(Number(e.target.value))}
                    min={0}
                    max={10000}
                    step={100}
                  />
                </label>
              </div>
            )}
          </div>
        )}

        {mode === 'xhr' && (
          <div className="subpanel">
            <h2>XHR/API Settings</h2>

            <div className="row rowWrap">
              <label className="field grow">
                <div className="label">API URL</div>
                <input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} placeholder="https://api..." />
              </label>

              <label className="field">
                <div className="label">Method</div>
                <div className="seg">
                  <button
                    className={xhrMethod === 'GET' ? 'segBtn active' : 'segBtn'}
                    onClick={() => setXhrMethod('GET')}
                  >
                    GET
                  </button>
                  <button
                    className={xhrMethod === 'POST' ? 'segBtn active' : 'segBtn'}
                    onClick={() => setXhrMethod('POST')}
                  >
                    POST
                  </button>
                </div>
              </label>
            </div>

            <div className="row rowWrap">
              <label className="field grow">
                <div className="label">Query Params (JSON)</div>
                <textarea value={paramsJson} onChange={(e) => setParamsJson(e.target.value)} rows={2} />
                {!paramsParsed.ok && <div className="hint err">{paramsParsed.error}</div>}
              </label>
            </div>

            {xhrMethod === 'POST' && (
              <div className="row rowWrap">
                <label className="field grow">
                  <div className="label">Request Body (JSON)</div>
                  <textarea
                    value={bodyJson}
                    onChange={(e) => setBodyJson(e.target.value)}
                    rows={4}
                    placeholder='{"query": "...", "variables": {...}}'
                  />
                  {!bodyParsed.ok ? <div className="hint err">{bodyParsed.error}</div> : <div className="hint">Required for GraphQL or POST APIs.</div>}
                </label>
              </div>
            )}

            <div className="row rowWrap">
              <label className="field grow">
                <div className="label">Cookies (JSON)</div>
                <textarea
                  value={cookiesJson}
                  onChange={(e) => setCookiesJson(e.target.value)}
                  rows={2}
                  placeholder='{"session_id": "..."}'
                />
                {!cookiesParsed.ok ? <div className="hint err">{cookiesParsed.error}</div> : <div className="hint">For authenticated endpoints.</div>}
              </label>
            </div>

            <div className="row rowWrap">
              <label className="field">
                <div className="label">Delay (ms)</div>
                <input
                  type="number"
                  value={xhrDelayMs}
                  onChange={(e) => setXhrDelayMs(Number(e.target.value))}
                  min={0}
                  max={10000}
                  step={100}
                />
              </label>

              <label className="field">
                <div className="label">Retries</div>
                <input
                  type="number"
                  value={xhrMaxRetries}
                  onChange={(e) => setXhrMaxRetries(Number(e.target.value))}
                  min={0}
                  max={5}
                />
              </label>
            </div>

            <h3>Pagination Strategy</h3>
            <div className="row rowWrap">
              <label className="field">
                <div className="label">Type</div>
                <select value={xhrPaginationType} onChange={(e) => setXhrPaginationType(e.target.value as any)}>
                  <option value="none">None (Single page)</option>
                  <option value="page_param">Page Param (page=1)</option>
                  <option value="offset">Offset/Limit (offset=0)</option>
                  <option value="cursor">Cursor (next_cursor)</option>
                </select>
              </label>
            </div>

            {xhrPaginationType === 'page_param' && (
              <div className="row rowWrap">
                <label className="field">
                  <div className="label">Param</div>
                  <input value={xhrPageParam} onChange={(e) => setXhrPageParam(e.target.value)} />
                </label>
                <label className="field">
                  <div className="label">Start</div>
                  <input type="number" value={xhrStart} onChange={(e) => setXhrStart(Number(e.target.value))} />
                </label>
                <label className="field">
                  <div className="label">End</div>
                  <input type="number" value={xhrEnd} onChange={(e) => setXhrEnd(Number(e.target.value))} />
                </label>
              </div>
            )}

            {xhrPaginationType === 'offset' && (
              <div className="row rowWrap">
                <label className="field">
                  <div className="label">Offset param</div>
                  <input value={xhrOffsetParam} onChange={(e) => setXhrOffsetParam(e.target.value)} />
                </label>
                <label className="field">
                  <div className="label">Limit param</div>
                  <input value={xhrLimitParam} onChange={(e) => setXhrLimitParam(e.target.value)} />
                </label>
                <label className="field">
                  <div className="label">Limit</div>
                  <input type="number" value={xhrLimit} onChange={(e) => setXhrLimit(Number(e.target.value))} />
                </label>
                <label className="field">
                  <div className="label">Max pages</div>
                  <input type="number" value={xhrMaxPages} onChange={(e) => setXhrMaxPages(Number(e.target.value))} />
                </label>
                <label className="field">
                  <div className="label">Start offset</div>
                  <input type="number" value={xhrStartOffset} onChange={(e) => setXhrStartOffset(Number(e.target.value))} />
                </label>
              </div>
            )}

            {xhrPaginationType === 'cursor' && (
              <div className="row rowWrap">
                <label className="field">
                  <div className="label">Cursor param</div>
                  <input value={xhrCursorParam} onChange={(e) => setXhrCursorParam(e.target.value)} />
                </label>
                <label className="field">
                  <div className="label">Cursor field (JSON path)</div>
                  <input value={xhrCursorField} onChange={(e) => setXhrCursorField(e.target.value)} />
                </label>
                <label className="field">
                  <div className="label">Initial cursor</div>
                  <input value={xhrInitialCursor} onChange={(e) => setXhrInitialCursor(e.target.value)} />
                </label>
                <label className="field">
                  <div className="label">Max pages</div>
                  <input type="number" value={xhrCursorMaxPages} onChange={(e) => setXhrCursorMaxPages(Number(e.target.value))} />
                </label>
              </div>
            )}

            <h3>Batch Execution</h3>
            <div className="row rowWrap">
              <label className="field grow">
                <div className="label">Batch Identifiers (comma-separated)</div>
                <textarea
                  value={xhrBatchIds}
                  onChange={(e) => setXhrBatchIds(e.target.value)}
                  rows={2}
                  placeholder="e.g. user1, user2, user3"
                />
                <div className="hint">Leave empty for single execution. Variables: {'{id}'} in URL or body.</div>
              </label>
            </div>
            {xhrBatchIds.trim() && (
              <div className="row rowWrap">
                <label className="field">
                  <div className="label">Variable Name</div>
                  <input value={xhrBatchVar} onChange={(e) => setXhrBatchVar(e.target.value)} />
                  <div className="hint">Default: "id". Replaces {'{id}'} or JSON key.</div>
                </label>
              </div>
            )}
          </div>
        )}

        {mode === 'selenium' && (
          <div className="subpanel">
            <h2>Selenium settings (explicit)</h2>
            <label className="check">
              <input type="checkbox" checked={seleniumEnabled} onChange={(e) => setSeleniumEnabled(e.target.checked)} />
              I understand Selenium is slower and a last resort
            </label>
            <div className="hint">
              Selenium is only used when you enable it. It may be blocked by some sites and can take minutes for multi-page pagination.
            </div>

            <div className="row rowWrap">
              <label className="field grow">
                <div className="label">CSS selector</div>
                <input value={cssSelector} onChange={(e) => setCssSelector(e.target.value)} placeholder=".companyCardWrapper" />
              </label>
              <label className="field">
                <div className="label">Wait time (s)</div>
                <input type="number" value={waitTime} onChange={(e) => setWaitTime(Number(e.target.value))} />
              </label>
            </div>

            <div className="row rowWrap">
              <label className="field grow">
                <div className="label">Cookies (JSON)</div>
                <textarea
                  value={cookiesJson}
                  onChange={(e) => setCookiesJson(e.target.value)}
                  rows={2}
                  placeholder='{"session_id": "..."}'
                />
                {!cookiesParsed.ok ? <div className="hint err">{cookiesParsed.error}</div> : <div className="hint">For authenticated sessions.</div>}
              </label>
            </div>

            <div className="row rowWrap">
              <label className="field">
                <div className="label">Scroll Count</div>
                <input
                  type="number"
                  value={selScrollCount}
                  onChange={(e) => setSelScrollCount(Number(e.target.value))}
                  min={0}
                  max={50}
                  placeholder="0 to disable"
                />
                <div className="hint">Useful for infinite scroll (e.g. 3).</div>
              </label>
              <label className="field">
                <div className="label">Scroll Delay (ms)</div>
                <input
                  type="number"
                  value={selScrollDelay}
                  onChange={(e) => setSelScrollDelay(Number(e.target.value))}
                  min={100}
                  max={10000}
                  step={100}
                />
              </label>
            </div>

            <label className="check">
              <input type="checkbox" checked={selUsePagination} onChange={(e) => setSelUsePagination(e.target.checked)} />
              Enable pagination (page param)
            </label>
            {selUsePagination && (
              <div className="row rowWrap">
                <label className="field">
                  <div className="label">Param</div>
                  <input value={selPageParam} onChange={(e) => setSelPageParam(e.target.value)} />
                </label>
                <label className="field">
                  <div className="label">Start</div>
                  <input type="number" value={selStart} onChange={(e) => setSelStart(Number(e.target.value))} />
                </label>
                <label className="field">
                  <div className="label">End</div>
                  <input type="number" value={selEnd} onChange={(e) => setSelEnd(Number(e.target.value))} />
                </label>
              </div>
            )}

            <h3>Batch Execution</h3>
            <div className="row rowWrap">
              <label className="field grow">
                <div className="label">Batch Identifiers (comma-separated)</div>
                <textarea
                  value={selBatchIds}
                  onChange={(e) => setSelBatchIds(e.target.value)}
                  rows={2}
                  placeholder="e.g. user1, user2, user3"
                />
                <div className="hint">Leave empty for single execution. Variables: {'{id}'} in URL.</div>
              </label>
            </div>
            {selBatchIds.trim() && (
              <div className="row rowWrap">
                <label className="field">
                  <div className="label">Variable Name</div>
                  <input value={selBatchVar} onChange={(e) => setSelBatchVar(e.target.value)} />
                  <div className="hint">Default: "id". Replaces {'{id}'} in URL.</div>
                </label>
              </div>
            )}
          </div>
        )}

        <div className="row actions">
          <button disabled={busy} onClick={runAnalyze}>
            {busy ? 'Extracting...' : 'Extract Data'}
          </button>
        </div>

        {error && <div className="alert err">{error}</div>}
      </section>

      <section className="panel">
        <h2>Result</h2>
        {!result ? (
          <div className="hint">Run an analysis to see output here.</div>
        ) : (
          <>
            <div className="kv">
              <div>
                <div className="k">Mode used</div>
                <div className="v">{result.mode_used}</div>
              </div>
              <div>
                <div className="k">Records</div>
                <div className="v">{result.record_count}</div>
              </div>
              <div>
                <div className="k">Has data</div>
                <div className="v">{String(result.has_data)}</div>
              </div>
            </div>
            <div className="msg">{result.message}</div>
            {result.csv_url && (
              <div className="row">
                <a className="btnLink" href={withBackendBase(result.csv_url)} target="_blank" rel="noreferrer">
                  Download CSV
                </a>
              </div>
            )}

            {/* Available Fields - Clickable chips */}
            {(() => {
              const fieldFilterTrace = result.decision_trace.find(t => t.step === 'field_filtering');
              const availableFields = (fieldFilterTrace?.details?.all_available_fields as string[]) || [];
              const matchedFields = (fieldFilterTrace?.details?.matched_fields as Record<string, string>) || {};
              const matchedActualFields = new Set(Object.values(matchedFields));

              if (availableFields.length > 0) {
                return (
                  <div className="availableFields">
                    <h3>Select Fields to Export</h3>
                    <p className="fieldDescription">
                      Click on the fields below to include them in your export. Selected fields will be highlighted.
                    </p>
                    <div className="fieldChips">
                      {availableFields.map((field) => {
                        const isSelected = matchedActualFields.has(field);
                        const isInInput = parsedRequestedFields.some(
                          rf => rf.toLowerCase().replace(/[^a-z0-9]/g, '') === field.toLowerCase().replace(/[^a-z0-9]/g, '')
                        );
                        return (
                          <button
                            key={field}
                            type="button"
                            className={`fieldChip ${isSelected ? 'selected' : ''} ${isInInput ? 'inInput' : ''}`}
                            onClick={() => {
                              if (isInInput) {
                                const newFields = parsedRequestedFields.filter(
                                  rf => rf.toLowerCase().replace(/[^a-z0-9]/g, '') !== field.toLowerCase().replace(/[^a-z0-9]/g, '')
                                );
                                setRequestedFields(newFields.join(', '));
                              } else {
                                const newFields = [...parsedRequestedFields, field];
                                setRequestedFields(newFields.join(', '));
                              }
                            }}
                            title={isInInput ? 'Click to deselect' : 'Click to select'}
                          >
                            {field}
                          </button>
                        );
                      })}
                    </div>

                    <div className="fieldSelectionActions">
                      <div className="selectedCount">
                        {parsedRequestedFields.length > 0
                          ? `${parsedRequestedFields.length} field(s) selected`
                          : 'No fields selected (all fields will be exported)'}
                      </div>
                      {parsedRequestedFields.length > 0 && (
                        <button
                          type="button"
                          className="runFilteredBtn"
                          onClick={runAnalyze}
                          disabled={busy}
                        >
                          {busy ? 'Extracting...' : 'Export Selected Fields'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              }
              return null;
            })()}

            <h3>Decision trace</h3>
            <div className="trace">
              {result.decision_trace.map((t, idx) => (
                <div key={idx} className={t.ok ? 'traceRow ok' : 'traceRow bad'}>
                  <div className="traceStep">{t.step}</div>
                  <div className="traceMeta">
                    {t.ok ? 'ok' : 'fail'}
                    {typeof t.ms === 'number' ? ` • ${t.ms}ms` : ''}
                  </div>
                  {t.details ? <pre className="traceDetails">{JSON.stringify(t.details, null, 2)}</pre> : null}
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  )
}

export default App
