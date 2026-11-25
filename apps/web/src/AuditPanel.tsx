import { useCallback, useEffect, useState } from 'react'

type AuditEvent = {
  id: string
  source_schema: string
  source_table: string
  operation: 'INSERT' | 'UPDATE' | 'DELETE'
  occurred_at: string
}

const PAGE_SIZE = 25

/** Shared-admin-only metadata history; intentionally no actor or row payload. */
export default function AuditPanel({ token }: { token: string }) {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [offset, setOffset] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const [opened, setOpened] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    if (!token) return
    setBusy(true)
    setError('')
    try {
      const response = await fetch('/api/v1/audit/events?limit=' + PAGE_SIZE + '&offset=' + offset, {
        headers: { Authorization: 'Bearer ' + token },
        cache: 'no-store',
      })
      if (!response.ok) throw new Error('Audit events unavailable (HTTP ' + response.status + ')')
      const payload = await response.json() as { events: AuditEvent[] }
      setEvents(payload.events)
      setLoaded(true)
    } catch (failure) {
      setEvents([])
      setError(failure instanceof Error ? failure.message : 'Unable to load audit events')
    } finally {
      setBusy(false)
    }
  }, [offset, token])

  useEffect(() => {
    setEvents([])
    setLoaded(false)
    setOffset(0)
    setError('')
    setOpened(false)
  }, [token])

  useEffect(() => {
    if (opened) void refresh()
  }, [opened, refresh])

  return <section className="data-panel audit-panel" aria-label="Administrative audit metadata">
    <div className="panel-header">
      <div>
        <h2>Change metadata</h2>
        <p>Administrator only · catalog and small objects · no row values or actor identities</p>
      </div>
      <button className="secondary small" disabled={busy} onClick={() => { if (opened) void refresh(); else setOpened(true) }}>
        {busy ? 'Loading…' : 'Refresh events'}
      </button>
    </div>
    {error && <p role="status" className="audit-notice">{error}</p>}
    {loaded && <div className="table-wrap">
      {events.length ? <table>
        <thead><tr><th>Event</th><th>Target</th><th>Operation</th><th>Timestamp</th></tr></thead>
        <tbody>{events.map(event => <tr key={event.id}>
          <td>{event.id}</td>
          <td>{event.source_schema}.{event.source_table}</td>
          <td>{event.operation}</td>
          <td><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time></td>
        </tr>)}</tbody>
      </table> : <div className="empty">No matching metadata events on this page.</div>}
    </div>}
    {!loaded && !error && <div className="empty">Select Refresh events to inspect metadata.</div>}
    {loaded && <div className="panel-footer">
      <span>Offset {offset} · Page size {PAGE_SIZE}</span>
      <div>
        <button className="secondary small" disabled={busy || offset === 0}
          onClick={() => { setOffset(Math.max(0, offset - PAGE_SIZE)); setLoaded(false) }}>Previous</button>
        <button className="secondary small" disabled={busy || events.length < PAGE_SIZE}
          onClick={() => { setOffset(offset + PAGE_SIZE); setLoaded(false) }}>Next</button>
      </div>
    </div>}
  </section>
}
