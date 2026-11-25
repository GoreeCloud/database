import { useCallback, useEffect, useState, type FormEvent } from 'react'

type StoredObject = {
  id: string
  filename: string
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
}
type Scope = 'unknown' | 'admin' | 'reader'

const MAX_BYTES = 1_048_576
const FILENAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/
const TYPES = new Set(['application/octet-stream', 'text/plain', 'image/png', 'image/jpeg', 'application/pdf'])

async function fetchAuthenticated(path: string, token: string, options: RequestInit = {}): Promise<Response> {
  const response = await fetch('/api' + path, {
    ...options,
    cache: 'no-store',
    headers: {
      ...options.headers,
      Authorization: 'Bearer ' + token,
    },
  })
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => ({}))
    const reason = typeof data === 'object' && data && 'detail' in data ? String(data.detail) : 'Request failed'
    throw new Error(reason + ' (HTTP ' + response.status + ')')
  }
  return response
}

export default function ObjectPanel({ token, scope }: { token: string, scope: Scope }) {
  const [objects, setObjects] = useState<StoredObject[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [loaded, setLoaded] = useState(false)

  const reload = useCallback(async () => {
    if (!token) return
    setBusy(true)
    try {
      const response = await fetchAuthenticated('/v1/objects?limit=50', token)
      const result = await response.json() as { objects: StoredObject[] }
      setObjects(result.objects)
      setLoaded(true)
      setMessage('')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to load objects')
    } finally {
      setBusy(false)
    }
  }, [token])

  useEffect(() => {
    setObjects([])
    setLoaded(false)
    // Do not automatically disclose object metadata until the user opens the section.
    setFile(null)
  }, [token])

  async function upload(event: FormEvent) {
    event.preventDefault()
    if (scope !== 'admin' || !file || busy) return
    const mime = file.type || 'application/octet-stream'
    if (!FILENAME.test(file.name)) { setMessage('Use an ASCII filename with letters, digits, dot, underscore or hyphen.'); return }
    if (!TYPES.has(mime)) { setMessage('Unsupported content type.'); return }
    if (file.size < 1 || file.size > MAX_BYTES) { setMessage('Choose a file between 1 byte and 1 MiB.'); return }
    setBusy(true)
    try {
      await fetchAuthenticated('/v1/objects?filename=' + encodeURIComponent(file.name), token, {
        method: 'POST', headers: { 'Content-Type': mime }, body: file,
      })
      setFile(null)
      setMessage('Object uploaded. All users with a viewer token can access it.')
      setLoaded(true)
      const response = await fetchAuthenticated('/v1/objects?limit=50', token)
      const result = await response.json() as { objects: StoredObject[] }
      setObjects(result.objects)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  async function download(item: StoredObject) {
    if (busy) return
    setBusy(true)
    try {
      const response = await fetchAuthenticated('/v1/objects/' + encodeURIComponent(item.id), token)
      const blob = await response.blob()
      if (blob.size !== item.size_bytes || blob.size > MAX_BYTES) throw new Error('File integrity size check failed')
      const localUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = localUrl
      anchor.download = item.filename
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(localUrl), 30_000)
      setMessage('Download requested for ' + item.filename)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Download failed')
    } finally {
      setBusy(false)
    }
  }

  return <section className="data-panel object-panel" aria-label="Private small objects">
    <div className="panel-header">
      <div><h2>Small objects</h2><p>Private schema · 1 MiB maximum · shared viewer access</p></div>
      <button className="secondary small" disabled={busy || scope === 'unknown'} onClick={() => void reload()}>Refresh objects</button>
    </div>
    {scope === 'admin' && <form className="object-upload" onSubmit={upload}>
      <label htmlFor="object-upload">Upload a small attachment (all viewer tokens can read it)</label>
      <input id="object-upload" type="file" accept=".txt,.png,.jpg,.jpeg,.pdf,application/octet-stream" disabled={busy}
        onChange={event => setFile(event.currentTarget.files?.[0] ?? null)} />
      <button type="submit" disabled={busy || !file}>Upload object</button>
    </form>}
    {message && <p className="object-message" role="status">{message}</p>}
    {loaded ? <div className="table-wrap">
      {objects.length ? <table><thead><tr><th>Filename</th><th>Size</th><th>Media type</th><th>Action</th></tr></thead>
        <tbody>{objects.map(item => <tr key={item.id}>
          <td>{item.filename}</td><td>{item.size_bytes.toLocaleString()} bytes</td><td>{item.media_type}</td>
          <td><button className="secondary small" disabled={busy} onClick={() => void download(item)}>Save</button></td>
        </tr>)}</tbody></table> : <p className="empty">No objects yet.</p>}
    </div> : <div className="empty">Choose Refresh objects to inspect stored attachments.</div>}
  </section>
}
