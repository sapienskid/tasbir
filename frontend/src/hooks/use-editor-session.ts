import { useEffect, useRef, useSyncExternalStore } from "react"
import { EditorSession, type EditorApi, type SessionCallbacks } from "@/lib/editor-session"
import type { EditorDoc } from "@/lib/editor-store"
import { getEditorState, refillFormat, refillPreview } from "@/lib/api"

const api: EditorApi = {
  getEditor: (t, f) => getEditorState(t, f),
  preview: (t, f, body, signal) => refillPreview(t, f, body, { signal }),
  refill: (t, f, body, opts) => refillFormat(t, f, body, opts),
}

// Sessions outlive their component while they still have unsaved work, so a
// route change or slide switch mid-save never loses an edit.
const registry = new Map<string, EditorSession>()

function acquire(taskId: string, fmt: string): EditorSession {
  const key = `${taskId}/${fmt}`
  let s = registry.get(key)
  if (!s) {
    s = new EditorSession(taskId, fmt, api)
    registry.set(key, s)
  }
  s.attached++
  return s
}

function release(s: EditorSession): void {
  s.attached--
  if (s.attached > 0) return
  void s.flush({ keepalive: true }).finally(() => {
    if (s.attached === 0 && !s.pending) {
      s.dispose()
      const key = `${s.taskId}/${s.fmt}`
      if (registry.get(key) === s) registry.delete(key)
    }
  })
}

let globalHooked = false
function hookGlobal(): void {
  if (globalHooked || typeof window === "undefined") return
  globalHooked = true
  const flushAll = () => {
    for (const s of registry.values()) if (s.pending) void s.flush({ keepalive: true })
  }
  window.addEventListener("pagehide", flushAll)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushAll()
  })
  window.addEventListener("beforeunload", (e) => {
    for (const s of registry.values()) {
      if (s.pending) {
        e.preventDefault()
        e.returnValue = ""
        return
      }
    }
  })
}

/**
 * Bind to the editing session for (task, format): restores editor state from
 * the server, and flushes unsaved edits when the component goes away.
 */
export function useEditorSession(
  taskId: string,
  fmt: string,
  loadHtml: () => Promise<string>,
  callbacks: SessionCallbacks
) {
  const sessionRef = useRef<EditorSession | null>(null)
  const keyRef = useRef("")
  const key = `${taskId}/${fmt}`
  if (keyRef.current !== key) {
    // Synchronous swap during render keeps the snapshot consistent with props.
    sessionRef.current = acquire(taskId, fmt)
    keyRef.current = key
  }
  const session = sessionRef.current as EditorSession
  session.callbacks = callbacks
  const loadRef = useRef(loadHtml)
  loadRef.current = loadHtml

  useEffect(() => {
    hookGlobal()
    const s = session
    // StrictMode mounts twice; the second acquire balances the first release.
    if (s.getSnapshot().phase === "loading" || !s.getSnapshot().info) {
      void s.load(() => loadRef.current())
    }
    return () => {
      release(s)
      // Drop our ref so a remount re-acquires (registry may have kept it).
      if (sessionRef.current === s) {
        sessionRef.current = null
        keyRef.current = ""
      }
    }
  }, [session])

  const snap = useSyncExternalStore(session.subscribe, session.getSnapshot)
  return { session, snap }
}

/** The store's document as React state (form fields, toggles, pickers). */
export function useEditorDoc(session: EditorSession): EditorDoc {
  return useSyncExternalStore(
    (cb) => session.store.subscribe(() => cb()),
    () => session.store.doc
  )
}
