import { useEffect, useState, type FormEvent, type ReactNode } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"
import useSWR from "swr"
import { ArrowLeft, Download, Loader2, RotateCcw, Shuffle } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { FitScaledFrame } from "@/components/tasks/preview-frame"
import { StatusBadge } from "@/components/tasks/status-badge"
import { useDesignSystems } from "@/hooks/use-library"
import { useTask } from "@/hooks/use-task"
import { apiRequest, downloadBlob, fetchBlob, fetchText } from "@/lib/api"
import { createCovers, DEFAULT_COVER, type CoverMeta, type CoverSettings } from "@/lib/covers"

const selectClass = "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return <div className="grid gap-2"><Label htmlFor={id}>{label}</Label>{children}</div>
}

export default function CoversPage() {
  const { taskId } = useParams<{ taskId: string }>()
  return taskId ? <CoverResults key={taskId} taskId={taskId} /> : <CoverForm />
}

function CoverForm() {
  const navigate = useNavigate()
  const location = useLocation()
  const { data: systems, error: systemsError } = useDesignSystems()
  const { data: meta, error: metaError } = useSWR<CoverMeta>("/covers/meta")
  const [settings, setSettings] = useState<CoverSettings>(() => {
    const saved = (location.state as { settings?: CoverSettings } | null)?.settings
    return { ...DEFAULT_COVER, ...saved, seed: saved?.seed || crypto.randomUUID() }
  })
  const [busy, setBusy] = useState(false)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [preview, setPreview] = useState("")
  const [previewKey, setPreviewKey] = useState("")
  const [error, setError] = useState("")
  const activeSystems = (systems ?? []).filter((system) => system.is_active)
  const dsId = settings.design_system_id || activeSystems.find((s) => s.id === "default")?.id || activeSystems[0]?.id || ""
  const request = { ...settings, design_system_id: dsId }
  const available = Boolean(meta && dsId && !systemsError && !metaError)
  const previewBody = JSON.stringify({ ...request, variations: 1 })
  const previewCurrent = Boolean(preview) && previewKey === previewBody
  const previewPending = settings.engine === "procedural" && available && (previewBusy || !previewCurrent)

  useEffect(() => {
    if (!available || settings.engine !== "procedural") {
      setPreview("")
      setPreviewKey("")
      setPreviewBusy(false)
      return
    }
    const controller = new AbortController()
    setPreviewBusy(true)
    setError("")
    const timer = setTimeout(() => {
      const payload = JSON.parse(previewBody) as CoverSettings
      if (!payload.seed.trim()) {
        setSettings((old) => old.seed.trim() ? old : { ...old, seed: crypto.randomUUID() })
        return
      }
      void apiRequest<{ html: string }>("/covers/preview", {
        method: "POST", body: previewBody, signal: controller.signal,
      }).then((response) => {
        if (controller.signal.aborted) return
        setPreview(response.html)
        setPreviewKey(previewBody)
      }).catch((err: unknown) => {
        if (controller.signal.aborted) return
        setPreview("")
        setPreviewKey("")
          setError(err instanceof Error ? err.message : "Preview failed")
      }).finally(() => {
        if (!controller.signal.aborted) setPreviewBusy(false)
      })
    }, 350)
    return () => { clearTimeout(timer); controller.abort() }
  }, [available, settings.engine, previewBody])

  function update<K extends keyof CoverSettings>(key: K, value: CoverSettings[K]) {
    setSettings((old) => ({ ...old, [key]: value }))
    setError("")
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!available || busy || previewPending) return
    setBusy(true)
    setError("")
    try {
      const response = await createCovers(request)
      navigate(`/covers/${response.task_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cover generation failed")
    } finally { setBusy(false) }
  }

  function randomizeSeed() {
    update("seed", crypto.randomUUID())
  }

  return (
    <div className="grid gap-8">
      <div className="max-w-2xl space-y-2">
        <p className="text-xs tracking-[0.18em] text-muted-foreground uppercase">Editorial artwork</p>
        <h1 className="font-display text-3xl font-semibold">Covers</h1>
        <p className="text-sm text-muted-foreground">Create a visual idea for your blog or newsletter. Artwork only, in your design system’s palette.</p>
      </div>
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(300px,440px)_1fr]">
        <form onSubmit={(event) => void submit(event)} className="grid gap-5">
          <fieldset disabled={busy} className="grid min-w-0 gap-5">
          <Field id="cover-system" label="Design system">
            <select id="cover-system" className={selectClass} value={dsId} onChange={(e) => update("design_system_id", e.target.value)}>
              {!dsId && <option value="">{systems ? "No active design systems" : "Loading…"}</option>}
              {activeSystems.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <Field id="cover-title" label="Article or newsletter title">
            <Input id="cover-title" value={settings.title} maxLength={300} placeholder="The limits of computation" onChange={(e) => update("title", e.target.value)} />
          </Field>
          <Field id="cover-content" label="Article context (optional)">
            <Textarea id="cover-content" value={settings.content} maxLength={20_000} rows={4} placeholder="Paste an excerpt or describe the central idea…" onChange={(e) => update("content", e.target.value)} />
          </Field>
          <Field id="cover-theme" label="Visual direction (optional)">
            <Textarea id="cover-theme" value={settings.theme} maxLength={1000} rows={2} placeholder="A flowing curve approaching a boundary of discrete blocks" onChange={(e) => update("theme", e.target.value)} />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field id="cover-engine" label="Artwork">
              <select id="cover-engine" className={selectClass} value={settings.engine} onChange={(e) => update("engine", e.target.value as CoverSettings["engine"])}>
                <option value="procedural">Procedural drawing</option>
                <option value="ai" disabled={!meta?.ai_available}>AI artwork</option>
              </select>
            </Field>
            <Field id="cover-ground" label="Ground">
              <select id="cover-ground" className={selectClass} value={settings.ground} onChange={(e) => update("ground", e.target.value as CoverSettings["ground"])}>
                <option value="white">Light</option><option value="black">Dark</option>
              </select>
            </Field>
          </div>
          {meta && !meta.ai_available && <p className="text-xs text-muted-foreground">AI artwork becomes available when Cloudflare Workers AI is configured.</p>}
          {settings.engine === "ai" && <p className="text-xs text-muted-foreground">Uses your Cloudflare image allowance. Generated artwork is recolored to your design system’s palette.</p>}
          <Field id="cover-motif" label="Composition">
            <select id="cover-motif" className={selectClass} value={settings.motif} onChange={(e) => update("motif", e.target.value)}>
              <option value="auto">From the article</option>
              <option value="random">Random composition</option>
              {(meta?.concepts ?? []).map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </Field>
          <Field id="cover-size" label="Canvas">
            <select id="cover-size" className={selectClass} value={`${settings.width}x${settings.height}`} onChange={(e) => {
              const [width, height] = e.target.value.split("x").map(Number)
              setSettings((old) => ({ ...old, width, height }))
              setPreview("")
            }}>
              {(meta?.sizes ?? [{ label: "Blog / newsletter · 16:9", width: 1600, height: 900 }]).map((size) => <option key={size.label} value={`${size.width}x${size.height}`}>{size.label}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field id="cover-placement" label="Visual weight">
              <select id="cover-placement" className={selectClass} value={settings.placement} onChange={(e) => update("placement", e.target.value as CoverSettings["placement"])}>
                <option value="center">Center</option><option value="left">Left</option><option value="right">Right</option>
              </select>
            </Field>
            <Field id="cover-texture" label="Surface">
              <select id="cover-texture" className={selectClass} value={settings.texture} onChange={(e) => update("texture", e.target.value as CoverSettings["texture"])}>
                <option value="print">Print texture</option><option value="clean">Clean</option>
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field id="cover-variations" label="Variations">
              <select id="cover-variations" className={selectClass} value={settings.variations} onChange={(e) => update("variations", Number(e.target.value))}>
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </Field>
            {settings.engine === "procedural" && <Field id="cover-seed" label="Drawing seed (optional)">
              <div className="flex min-w-0 gap-2">
                <Input id="cover-seed" className="min-w-0" value={settings.seed} maxLength={128} placeholder="Random" onChange={(e) => update("seed", e.target.value)} />
                <Button type="button" variant="outline" size="icon" aria-label="Randomize seed" title="Randomize seed" onClick={randomizeSeed}>
                  <Shuffle className="size-4" aria-hidden="true" />
                </Button>
              </div>
            </Field>}
          </div>
          {error || systemsError || metaError ? <p role="alert" className="text-sm text-destructive">{error || "Could not load cover settings. Refresh to try again."}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={!available || busy || previewPending || (settings.engine === "ai" && !meta?.ai_available)}>
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}Generate covers
            </Button>

          </div>
          </fieldset>
        </form>
        <div className="grid gap-4 lg:sticky lg:top-24">
          <div style={{ aspectRatio: `${settings.width}/${settings.height}` }} className="relative overflow-hidden rounded-lg border bg-muted/30" aria-busy={previewPending}>
            {preview ? <FitScaledFrame html={preview} width={settings.width} height={settings.height} gap={0} bordered={false} /> : <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
              <svg viewBox="0 0 200 110" className="w-48 text-muted-foreground" fill="none" stroke="currentColor" aria-hidden="true">
                <path d="M25 86H175M40 95V15" strokeWidth="1" opacity=".35" />
                <path d="M49 77C85 77 106 69 119 49S134 22 135 13" strokeWidth="2.5" />
                <path d="M145 14V88" strokeDasharray="3 5" /><circle cx="164" cy="34" r="8" />
              </svg>
              <p className="text-sm text-muted-foreground">{settings.engine === "procedural" ? "Your drawing preview updates automatically as you adjust the settings." : "Generate covers to explore textured artwork for your article."}</p>
            </div>}
            {previewPending && <div role="status" className="absolute right-3 bottom-3 flex items-center gap-2 rounded-md border bg-background/95 px-3 py-2 text-xs"><Loader2 className="size-3 animate-spin" aria-hidden="true" />Updating preview…</div>}
          </div>
          <div className="flex justify-between text-xs text-muted-foreground"><span>{settings.width} × {settings.height}</span><span>PNG · SVG · HTML</span></div>
          <p className="max-w-lg text-sm text-muted-foreground">One visual idea, room to breathe. Titles and typography stay separate so you can use the artwork across your blog, newsletter, and social posts.</p>
        </div>
      </div>
    </div>
  )
}

function CoverResults({ taskId }: { taskId: string }) {
  const { task, files, error, mutate } = useTask(taskId)
  const [retrying, setRetrying] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const running = task?.status === "pending" || task?.status === "running"
  async function retry() {
    setRetrying(true)
    try { await apiRequest(`/tasks/${taskId}/retry`, { method: "POST" }); await mutate() }
    catch (err) { toast.error(err instanceof Error ? err.message : "Retry failed") }
    finally { setRetrying(false) }
  }
  async function archive() {
    setDownloading(true)
    try { downloadBlob(await fetchBlob(`/tasks/${taskId}/files/archive`), `covers-${taskId}.zip`) }
    catch (err) { toast.error(err instanceof Error ? err.message : "Download failed") }
    finally { setDownloading(false) }
  }
  if (error) return <p role="alert" className="text-destructive">{error.message}</p>
  if (!task) return <p>Loading covers…</p>
  if (task.source_data.mode !== "cover") return <p>This task is not a cover. <Link to={`/tasks/${taskId}`} className="underline">Open task</Link></p>
  const entries = Object.entries(task.result?.platforms ?? {})
  const width = Number(task.source_data.width || 1600)
  const height = Number(task.source_data.height || 900)
  return <div className="grid gap-6">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3"><Button asChild variant="ghost" size="icon" aria-label="Back to covers"><Link to="/covers"><ArrowLeft className="size-4" /></Link></Button><div><h1 className="font-display text-2xl font-semibold">{String(task.source_data.title || "Untitled cover")}</h1><p className="text-sm text-muted-foreground">Cover studies · {width} × {height}</p></div><StatusBadge status={task.status} /></div>
      <div className="flex flex-wrap gap-2">
        <Button asChild variant="outline"><Link to="/covers" state={{ settings: { ...task.source_data, seed: "" } }}>Use these settings</Link></Button>
        {task.status === "failed" && <Button variant="outline" onClick={() => void retry()} disabled={retrying}><RotateCcw className="size-4" aria-hidden="true" />Retry failed covers</Button>}
        {files.length > 0 && <Button onClick={() => void archive()} disabled={downloading}><Download className="size-4" aria-hidden="true" />Download all</Button>}
      </div>
    </div>
    {running && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" aria-hidden="true" />Creating your cover variations. You can leave this page and return from Tasks.</p>}
    {task.error && <p role="alert" className="text-sm text-destructive">{task.error}</p>}
    <div className="grid gap-6 xl:grid-cols-2">
      {entries.map(([format, entry]) => <div key={format} className="grid gap-3 rounded-lg border p-4">
        {files.some((f) => f.filename === `${format}.html`) && <CoverPreview taskId={taskId} format={format} width={width} height={height} />}
        <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-sm font-medium">Study {format.split("-").at(-1)}</span><div className="flex gap-2">
          {["png", "svg", "html"].filter((ext) => files.some((f) => f.filename === `${format}.${ext}`)).map((ext) => <CoverDownload key={ext} taskId={taskId} filename={`${format}.${ext}`} label={ext.toUpperCase()} />)}
        </div></div>
        {entry.error && <p className="text-sm text-destructive">{entry.error}</p>}
      </div>)}
    </div>
    {!running && !files.length && !task.error && <p className="text-sm text-muted-foreground">These cover files have expired. Use these settings to generate another set.</p>}
    {task.source_data.engine === "ai" && !running && <p className="text-xs text-muted-foreground">Check generated artwork for unwanted lettering before publishing.</p>}
  </div>
}

function CoverPreview({ taskId, format, width, height }: { taskId: string; format: string; width: number; height: number }) {
  const path = `/tasks/${taskId}/files/${format}.html?consume=false`
  const { data: html, error } = useSWR(path, fetchText)
  return <div style={{ aspectRatio: `${width}/${height}` }} className="overflow-hidden bg-muted/30">
    {html ? <FitScaledFrame html={html} width={width} height={height} gap={0} bordered={false} /> : <p className="p-4 text-sm text-muted-foreground">{error ? "Preview unavailable. Download the artwork to view it." : "Loading preview…"}</p>}
  </div>
}

function CoverDownload({ taskId, filename, label }: { taskId: string; filename: string; label: string }) {
  const [busy, setBusy] = useState(false)
  async function download() {
    setBusy(true)
    try { downloadBlob(await fetchBlob(`/tasks/${taskId}/files/${filename}?consume=false`), filename) }
    catch (err) { toast.error(err instanceof Error ? err.message : "Download failed") }
    finally { setBusy(false) }
  }
  return <Button size="sm" variant="outline" disabled={busy} onClick={() => void download()} aria-label={`Download ${filename}`}>{label}</Button>
}
