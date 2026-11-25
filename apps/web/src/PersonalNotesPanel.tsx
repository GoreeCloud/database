import { useEffect, useRef, useState, type FormEvent } from 'react'

type PersonalNote = {
  id: string
  title: string
  content: string
  created_at: string
}
const PAGE_SIZE = 25
const REQUIRES_OIDC = 'Private notes require an operator-configured, signed OIDC access token. Shared admin/viewer tokens are not personal identities.'

/** Opt-in, client-memory-only notes view; server PostgreSQL RLS owns isolation. */
export default function PersonalNotesPanel({ token }: { token: string }) {
  const [opened, setOpened] = useState(false)
  const [authorized, setAuthorized] = useState(false)
  const [notes, setNotes] = useState<PersonalNote[]>([])
  const [offset, setOffset] = useState(0)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [editing, setEditing] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<PersonalNote | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const controller = useRef<AbortController | null>(null)
  const generation = useRef(0)

  useEffect(() => {
    generation.current += 1
    controller.current?.abort()
    setOpened(false)
    setAuthorized(false)
    setNotes([])
    setTitle('')
    setContent('')
    setEditing(false)
    setPendingDelete(null)
    setMessage('')
    setOffset(0)
    setBusy(false)
    return () => { generation.current += 1; controller.current?.abort() }
  }, [token])

  function close() {
    generation.current += 1
    controller.current?.abort()
    setOpened(false)
    setAuthorized(false)
    setNotes([])
    setTitle('')
    setContent('')
    setEditing(false)
    setPendingDelete(null)
    setMessage('')
    setOffset(0)
    setBusy(false)
  }

  async function loadPage(nextOffset: number, force = false) {
    if ((!force && busy) || !token) return
    const revision = generation.current
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setBusy(true)
    setMessage('')
    try {
      const response = await fetch('/api/v1/me/notes?limit=' + PAGE_SIZE + '&offset=' + nextOffset, {
        headers: { Authorization: 'Bearer ' + token },
        signal: request.signal,
        cache: 'no-store',
      })
      if (response.status === 401) throw new Error(REQUIRES_OIDC)
      if (!response.ok) throw new Error('Private notes unavailable (HTTP ' + response.status + ')')
      const result = await response.json() as { notes: PersonalNote[] }
      if (request.signal.aborted || revision !== generation.current) return
      setNotes(result.notes)
      setAuthorized(true)
      setOffset(nextOffset)
      setOpened(true)
    } catch (error) {
      if (request.signal.aborted || revision !== generation.current) return
      setNotes([])
      setAuthorized(false)
      setMessage(error instanceof Error ? error.message : 'Private notes are unavailable')
      setOpened(true)
    } finally {
      if (revision === generation.current) setBusy(false)
    }
  }

  async function deleteConfirmed() {
    const note = pendingDelete
    if (busy || !opened || !authorized || !note || !token) return
    const revision = generation.current
    setBusy(true)
    setMessage('')
    try {
      const response = await fetch('/api/v1/me/notes/' + encodeURIComponent(note.id), {
        method: 'DELETE',
        headers: {
          Authorization: 'Bearer ' + token,
          'X-GC-Confirm-Delete': 'delete-my-note',
        },
        cache: 'no-store',
      })
      if (response.status === 401) throw new Error('Deleting a private note requires a signed token with both read and write scopes.')
      if (response.status === 404) throw new Error('Note not found for this signed subject.')
      if (!response.ok) throw new Error('Unable to remove private note (HTTP ' + response.status + ')')
      if (revision !== generation.current) return
      setPendingDelete(null)
      setBusy(false)
      await loadPage(offset, true)
      setMessage('Note removed from the active database. Backups may retain copies.')
    } catch (error) {
      if (revision === generation.current) setMessage(error instanceof Error ? error.message : 'Private note deletion failed')
    } finally {
      if (revision === generation.current) setBusy(false)
    }
  }

  async function createNote(event: FormEvent) {
    event.preventDefault()
    if (busy || !opened || !title.trim() || !content.trim()
        || title.length > 120 || content.length > 2048
        || new TextEncoder().encode(content).length > 8192) return
    const revision = generation.current
    setBusy(true)
    setMessage('')
    try {
      const response = await fetch('/api/v1/me/notes', {
        method: 'POST',
        headers: {
          Authorization: 'Bearer ' + token,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: title.trim(), content: content.trim() }),
        cache: 'no-store',
      })
      if (response.status === 401) throw new Error('Creating notes requires a signed OIDC token with both database.read and database.write scopes.')
      if (!response.ok) throw new Error('Unable to create note (HTTP ' + response.status + ')')
      if (revision !== generation.current) return
      setTitle('')
      setContent('')
      setEditing(false)
      setBusy(false)
      await loadPage(0, true)
    } catch (error) {
      if (revision === generation.current) setMessage(error instanceof Error ? error.message : 'Unable to save note')
    } finally {
      if (revision === generation.current) setBusy(false)
    }
  }

  return <section className="data-panel personal-notes-panel" aria-label="Personal notes">
    <div className="panel-header">
      <div>
        <h2>Personal notes</h2>
        <p>Opt-in · signed OIDC only · PostgreSQL subject isolation · no local storage</p>
      </div>
      <button className="secondary small" disabled={busy} onClick={() => opened ? close() : void loadPage(0)}>
        {opened ? 'Clear and close' : 'Open private notes'}
      </button>
    </div>
    {opened && <>
      {message && <p className="personal-message" role="status">{message}</p>}
      {authorized && <><div className="personal-actions">
        <button className="secondary small" disabled={busy} onClick={() => void loadPage(offset)}>Refresh</button>
        <button className="secondary small" disabled={busy} onClick={() => setEditing(v => !v)}>
          {editing ? 'Cancel editor' : 'Create note'}
        </button>
      </div>
      {pendingDelete && <div className="personal-confirm" role="alertdialog" aria-label="Confirm private-note deletion">
        <strong>Delete this note from the active database?</strong>
        <p><strong>{pendingDelete.title}</strong> will be permanently removed from the live notes table. Backups may retain copies.</p>
        <div className="personal-actions">
          <button className="secondary small" disabled={busy} onClick={() => setPendingDelete(null)}>Cancel</button>
          <button className="small" disabled={busy} onClick={() => void deleteConfirmed()}>Confirm delete my note</button>
        </div>
      </div>}
      {editing && <form className="personal-form" onSubmit={event => void createNote(event)}>
        <label htmlFor="private-note-title">Note title</label>
        <input id="private-note-title" autoComplete="off" maxLength={120} value={title}
          onChange={event => setTitle(event.currentTarget.value)} required />
        <label htmlFor="private-note-body">Private note</label>
        <textarea id="private-note-body" rows={4} maxLength={2048} value={content}
          onChange={event => setContent(event.currentTarget.value)} required />
        <button type="submit" disabled={busy || !title.trim() || !content.trim()}>Save with signed OIDC token</button>
      </form>}
      <div className="personal-notes">
        {notes.map(note => <article className="personal-note" key={note.id}>
          <h3>{note.title}</h3>
          <time dateTime={note.created_at}>{new Date(note.created_at).toLocaleString()}</time>
          <p>{note.content}</p>
          <button className="secondary small" disabled={busy} onClick={() => setPendingDelete(note)}>Delete note</button>
        </article>)}
        {notes.length === 0 && !busy && <p className="empty">No notes visible for this signed subject.</p>}
      </div>
      <div className="panel-footer">
        <span>Offset {offset} · {notes.length} notes on this page</span>
        <div>
          <button className="secondary small" disabled={busy || offset === 0}
            onClick={() => void loadPage(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
          <button className="secondary small" disabled={busy || notes.length < PAGE_SIZE}
            onClick={() => void loadPage(offset + PAGE_SIZE)}>Next</button>
        </div>
      </div></>}
    </>}
    {!opened && <p className="personal-hint">Only a verified, short-lived OIDC identity can access notes. Shared management tokens do not identify a person.</p>}
  </section>
}
