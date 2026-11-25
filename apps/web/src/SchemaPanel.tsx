import { useEffect, useState } from 'react'

type SchemaColumn = {
  name: string
  type: string
  database_type: string
  nullable: boolean
  default: string | null
  ordinal: number
  max_length: number | null
  primary_key: boolean
}
type SchemaIndex = { name: string, definition: string }
type TableDescription = { schema: string, table: string, columns: SchemaColumn[], indexes: SchemaIndex[] }

export default function SchemaPanel({
  token, schema, table,
}: { token: string, schema: string, table: string }) {
  const [expanded, setExpanded] = useState(false)
  const [details, setDetails] = useState<TableDescription | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setDetails(null)
    setError('')
    setExpanded(false)
  }, [token, schema, table])

  useEffect(() => {
    if (!expanded) return
    const controller = new AbortController()
    setLoading(true)
    setError('')
    void (async () => {
      try {
        const response = await fetch(
          '/api/v1/tables/' + encodeURIComponent(schema) + '/' + encodeURIComponent(table) + '/schema',
          {
            headers: { Authorization: 'Bearer ' + token },
            cache: 'no-store',
            signal: controller.signal,
          },
        )
        if (!response.ok) throw new Error('Schema inspection failed (HTTP ' + response.status + ')')
        const data = await response.json() as TableDescription
        if (!controller.signal.aborted) setDetails(data)
      } catch (error) {
        if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Unable to inspect schema')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    })()
    return () => { controller.abort() }
  }, [expanded, token, schema, table])

  return <section className="data-panel schema-panel" aria-label="Read-only table schema">
    <div className="panel-header">
      <div><h2>Schema inspection</h2><p>Column types · primary keys · indexes · read-only metadata</p></div>
      <button className="secondary small" aria-expanded={expanded} onClick={() => setExpanded(open => !open)}>
        {expanded ? 'Hide schema' : 'Inspect schema'}
      </button>
    </div>
    {expanded && <>
      {loading && <p className="schema-status">Loading schema…</p>}
      {error && <p className="schema-status" role="status">{error}</p>}
      {details && <>
        <div className="table-wrap">
          <table><thead><tr><th>Column</th><th>Data type</th><th>Nulls</th><th>Default</th></tr></thead>
            <tbody>{details.columns.map(column => <tr key={column.name}>
              <td>{column.name} {column.primary_key && <span className="schema-pk">PRIMARY KEY</span>}</td>
              <td>{column.type}</td>
              <td>{column.nullable ? 'Allowed' : 'Not null'}</td>
              <td>{column.default ?? '—'}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <div className="schema-indexes">
          <h3>Indexes ({details.indexes.length})</h3>
          {details.indexes.map(index => <div key={index.name} className="schema-index">
            <strong>{index.name}</strong>
            <code>{index.definition}</code>
          </div>)}
          {!details.indexes.length && <p>No indexes reported.</p>}
        </div>
      </>}
    </>}
  </section>
}
