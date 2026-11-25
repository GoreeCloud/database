import { useCallback, useEffect, useState, type FormEvent } from 'react'
import SchemaPanel from './SchemaPanel'
import ObjectPanel from './ObjectPanel'

type Table = { schema: string; name: string }
type Rows = { schema: string; table: string; columns: string[]; rows: Record<string, unknown>[]; limit: number; offset: number }

async function api<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api' + path, {
    ...options,
    headers: {
      Authorization: 'Bearer ' + token,
      ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
    },
    cache: 'no-store',
  })
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => ({}))
    const detail = typeof data === 'object' && data && 'detail' in data ? String(data.detail) : 'Request failed'
    throw new Error(detail + ' (HTTP ' + response.status + ')')
  }
  return response.json() as Promise<T>
}

function display(value: unknown): string {
  if (value === null || value === undefined) return 'NULL'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export default function App() {
  const [entry, setEntry] = useState('')
  const [token, setToken] = useState('')
  const [scope, setScope] = useState<'unknown' | 'admin' | 'reader'>('unknown')
  const [tables, setTables] = useState<Table[]>([])
  const [selected, setSelected] = useState<Table | null>(null)
  const [data, setData] = useState<Rows | null>(null)
  const [offset, setOffset] = useState(0)
  const [liveRevision, setLiveRevision] = useState(0)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [insertOpen, setInsertOpen] = useState(false)
  const [payload, setPayload] = useState('{"slug":"example","description":"Created in GoreeCloud Database"}')

  useEffect(() => {
    if (!token) { setScope('unknown'); return }
    let active = true
    setScope('unknown')
    api<{ scope: 'admin' | 'reader' }>('/v1/session', token)
      .then(result => { if (active) setScope(result.scope === 'admin' ? 'admin' : 'reader') })
      .catch(() => { if (active) setScope('unknown') })
    return () => { active = false }
  }, [token])

  const loadTables = useCallback(async (currentToken: string) => {
    setLoading(true)
    setMessage('')
    try {
      const result = await api<{ tables: Table[] }>('/v1/tables', currentToken)
      setTables(result.tables)
      setSelected(previous => result.tables.find(t => t.name === previous?.name) ?? result.tables[0] ?? null)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to load database')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!selected || !token || selected.name !== 'catalog') return
    const controller = new AbortController()
    void (async () => {
      try {
        const response = await fetch('/api/v1/events/catalog', {
          headers: { Authorization: 'Bearer ' + token, Accept: 'text/event-stream' },
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok || !response.body) return
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let pending = ''
        while (!controller.signal.aborted) {
          const { done, value } = await reader.read()
          if (done) break
          pending += decoder.decode(value, { stream: true })
          const frames = pending.split('\n\n')
          pending = frames.pop() ?? ''
          if (frames.some(frame => frame.split('\n').includes('event: catalog'))) {
            setLiveRevision(value => value + 1)
          }
        }
      } catch {
        // Streaming is a best-effort preview. Manual refresh always works.
      }
    })()
    return () => { controller.abort() }
  }, [selected?.name, token])

  useEffect(() => {
    if (!selected || !token) return
    let cancelled = false
    setLoading(true)
    setMessage('')
    setData(null)
    api<Rows>(`/v1/tables/${encodeURIComponent(selected.schema)}/${encodeURIComponent(selected.name)}/rows?limit=25&offset=${offset}`, token)
      .then(result => { if (!cancelled) setData(result) })
      .catch(error => { if (!cancelled) setMessage(error instanceof Error ? error.message : 'Request failed') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [selected, token, offset, liveRevision])

  function connect(event: FormEvent) {
    event.preventDefault()
    if (!entry.trim()) return
    setToken(entry.trim())
    setEntry('')
    setOffset(0)
    void loadTables(entry.trim())
  }

  async function addRow(event: FormEvent) {
    event.preventDefault()
    if (!selected || scope !== 'admin') return
    try {
      const obj: unknown = JSON.parse(payload)
      if (obj === null || Array.isArray(obj) || typeof obj !== 'object') throw new Error('Enter a JSON object')
      await api(`/v1/tables/${encodeURIComponent(selected.schema)}/${encodeURIComponent(selected.name)}/rows`, token, {
        method: 'POST', body: JSON.stringify(obj),
      })
      setInsertOpen(false)
      setMessage('Row inserted. Select Refresh to reload the table.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Insert failed')
    }
  }

  function disconnect() {
    setToken('')
    setScope('unknown')
    setInsertOpen(false)
    setEntry('')
    setSelected(null)
    setTables([])
    setData(null)
    setMessage('')
  }

  if (!token) return <main className="auth-shell">
    <section className="auth-card">
      <div className="logo-mark" aria-hidden="true">G</div>
      <p className="eyebrow">GOREECLOUD · SELF-HOSTED</p>
      <h1>Database control, without the cloud dependency.</h1>
      <p className="muted">Connect with the generated administrator or viewer token. The viewer token cannot insert rows. This preview does not store credentials on disk.</p>
      <form onSubmit={connect} className="stack">
        <label htmlFor="token">Admin or read-only token</label>
        <input autoFocus id="token" type="password" autoComplete="off" value={entry} onChange={e => setEntry(e.target.value)} placeholder="Paste GC_ADMIN_TOKEN or GC_READ_TOKEN" />
        <button type="submit" disabled={!entry.trim()}>Connect to database</button>
      </form>
      <p className="hint">Local development preview · Never expose this console directly to the Internet.</p>
    </section>
  </main>

  return <div className="layout">
    <aside className="sidebar">
      <div className="brand"><span className="brand-icon">G</span><span><strong>GoreeCloud</strong><small>DATABASE</small></span></div>
      <div className="nav-label">WORKSPACE</div>
      <div className="nav-active">▦ <span>Table explorer</span></div>
      <div className="nav-label space-top">SCHEMA · APP</div>
      <nav aria-label="Database tables">
        {tables.map(table => <button key={table.schema + table.name} className={'table-link ' + (selected?.name === table.name ? 'active' : '')} onClick={() => { setSelected(table); setOffset(0); setInsertOpen(false) }}>
          <span className="table-glyph">▤</span>{table.name}
        </button>)}
      </nav>
      <div className="sidebar-bottom"><span className="status-dot" /> Local development <button className="link-button" onClick={disconnect}>Disconnect</button></div>
    </aside>
    <main className="content">
      <header className="topbar"><span>Workspace <span className="chevron">/</span> app <span className="chevron">/</span> {selected?.name ?? 'Tables'}</span><span className="preview-pill">DEVELOPMENT PREVIEW</span></header>
      <div className="main-inner">
        <div className="heading-row"><div><p className="eyebrow">POSTGRESQL / SCHEMA EXPLORER</p><h1>{selected?.name ?? 'Your database'}</h1><p className="muted">Inspect and manage your application data with parameterized operations.</p></div><div className="actions"><button className="secondary" onClick={() => { if (selected) setSelected({ ...selected }); else void loadTables(token) }} disabled={loading}>↻ Refresh</button><button onClick={() => setInsertOpen(open => !open)} disabled={!selected || scope !== 'admin'}>{scope === 'reader' ? 'Read-only access' : '+ Insert row'}</button></div></div>
        {message && <div role="status" className="alert">{message} <button className="dismiss" onClick={() => setMessage('')}>Dismiss</button></div>}
        <div className="stat-grid"><div className="stat"><span>Tables available</span><strong>{tables.length}</strong><small>App schema</small></div><div className="stat"><span>Page size</span><strong>25</strong><small>Rows per request</small></div><div className="stat"><span>Connection</span><strong className="connected"><span className="status-dot" /> Secured</strong><small>{scope === 'admin' ? 'Admin · read/write' : scope === 'reader' ? 'Viewer · read-only' : 'Verifying access…'}</small></div></div>
        {insertOpen && scope === 'admin' && <form className="insert-panel" onSubmit={addRow}><h2>Insert JSON row</h2><p className="muted">Flat JSON keys must match existing columns. Database constraints remain authoritative.</p><textarea aria-label="JSON row" spellCheck={false} value={payload} onChange={e => setPayload(e.target.value)} rows={4}/><button type="submit">Insert row</button></form>}
        <section className="data-panel" aria-label="Database rows">
          <div className="panel-header"><div><h2>Table data</h2><p>{selected ? `app.${selected.name}` + (selected.name === 'catalog' ? ' · live metadata updates' : '') : 'No table selected'}</p></div><span className="pill">{loading ? 'Loading…' : `${data?.rows.length ?? 0} rows`}</span></div>
          <div className="table-wrap">
            {data ? <table><thead><tr>{data.columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{data.rows.map((row, i) => <tr key={i}>{data.columns.map(col => <td key={col} title={display(row[col])}>{display(row[col])}</td>)}</tr>)}</tbody></table> : <div className="empty">{loading ? 'Loading data…' : 'Select a table to inspect its rows.'}</div>}
            {data && data.rows.length === 0 && <div className="empty">No rows on this page.</div>}
          </div>
          <div className="panel-footer"><span>Showing offset {offset}</span><div><button className="secondary small" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</button><button className="secondary small" disabled={loading || (data?.rows.length ?? 0) < 25} onClick={() => setOffset(offset + 25)}>Next</button></div></div>
        </section>
        {selected && <SchemaPanel token={token} schema={selected.schema} table={selected.name} />}
        <ObjectPanel token={token} scope={scope} />
        <p className="footnote">GoreeCloud UI alpha palette · No public hosting · Data remains on your configured self-hosted database.</p>
      </div>
    </main>
  </div>
}
