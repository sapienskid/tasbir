import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowLeft, Loader2, Plus, Save, Trash2, Wand2 } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { Dropzone } from "@/components/tasks/dropzone"
import { ScaledFrame } from "@/components/tasks/preview-frame"
import {
  createDesignSystemFromInput,
  getDesignSystem,
  removeLogo,
  updateDesignSystem,
  uploadLogo,
  type DesignSystem,
} from "@/lib/api"
import { useDesignSystems, useAgentJob, isJobDone } from "@/hooks/use-library"

const COLOR_TOKENS = new Set([
  "--color-bg",
  "--color-bg-inverted",
  "--color-text",
  "--color-text-inverted",
  "--color-text-secondary",
  "--color-text-tertiary",
  "--color-border",
  "--color-border-inverted",
  "--color-accent",
])

export default function DesignSystemsPage() {
  const { data: systems, isLoading, mutate } = useDesignSystems()
  const [dsId, setDsId] = useState<string>("")
  const [draft, setDraft] = useState<DesignSystem | null>(null)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const { data: job } = useAgentJob(jobId)

  const activeSystems = useMemo(() => (systems ?? []).filter((s) => s.is_active), [systems])
  const current = useMemo(
    () => activeSystems.find((s) => s.id === dsId) ?? activeSystems[0],
    [activeSystems, dsId]
  )

  // Keep a fresh full draft whenever the selected system changes.
  useEffect(() => {
    if (!current) {
      setDraft(null)
      return
    }
    let alive = true
    getDesignSystem(current.id)
      .then((full) => {
        if (alive) {
          setDraft(structuredClone(full))
          setDsId(full.id)
        }
      })
      .catch(() => {
        if (alive) setDraft(structuredClone(current))
      })
    return () => {
      alive = false
    }
  }, [current?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function save() {
    if (!draft) return
    setSaving(true)
    try {
      await updateDesignSystem(draft.id, {
        name: draft.name,
        description: draft.description,
        brand: draft.brand,
        footer: draft.footer,
        categories: draft.categories,
        overrides: draft.overrides,
        tokens: draft.tokens,
        token_roles: draft.token_roles,
        campaigns: draft.campaigns,
        design_instruction: draft.design_instruction,
      })
      toast.success("Design system saved")
      void mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function handleLogo(file: File) {
    if (!draft) return
    try {
      await uploadLogo(draft.id, file)
      toast.success("Logo uploaded")
      const fresh = await getDesignSystem(draft.id)
      setDraft(fresh)
      void mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Logo upload failed")
    }
  }

  async function handleRemoveLogo() {
    if (!draft) return
    try {
      await removeLogo(draft.id)
      const fresh = await getDesignSystem(draft.id)
      setDraft(fresh)
      void mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Remove failed")
    }
  }

  if (isLoading && !systems) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }

  if (systems && activeSystems.length === 0) {
    return (
      <div className="grid gap-4">
        <h1 className="text-xl font-semibold">Design Systems</h1>
        <p className="text-sm text-muted-foreground">
          No design systems yet — create one with the brand builder.
        </p>
        <div>
          <Button onClick={() => setCreateOpen(true)}>
            <Wand2 className="size-4" />
            Create with AI
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" aria-label="Back">
            <Link to="/">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-xl font-semibold">Design Systems</h1>
            <p className="text-sm text-muted-foreground">
              Brand identity, tokens, campaigns, and rules — fully editable.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={current?.id ?? ""} onValueChange={(v) => setDsId(v)}>
            <SelectTrigger className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {activeSystems.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={() => setCreateOpen(true)}>
            <Wand2 className="size-4" />
            Create with AI
          </Button>
        </div>
      </div>

      {!draft ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Input
                className="w-72"
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                aria-label="Design system name"
              />
              <Badge variant="outline">{draft.id}</Badge>
              <Badge variant={draft.is_active ? "default" : "outline"}>
                {draft.source}
              </Badge>
            </div>
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="size-4 animate-spin" /> Saving…
                </>
              ) : (
                <>
                  <Save className="size-4" /> Save
                </>
              )}
            </Button>
          </div>

          <Tabs defaultValue="brand">
            <TabsList className="flex-wrap">
              <TabsTrigger value="brand">Brand</TabsTrigger>
              <TabsTrigger value="tokens">Tokens</TabsTrigger>
              <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
              <TabsTrigger value="advanced">Advanced</TabsTrigger>
              <TabsTrigger value="preview">Preview</TabsTrigger>
            </TabsList>

            <TabsContent value="brand" className="grid gap-4">
              <Card>
                <CardContent className="grid gap-4 p-6">
                  <div className="grid gap-2">
                    <Label>Description</Label>
                    <Textarea
                      value={draft.description}
                      onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <BrandField label="Brand name" value={draft.brand.name ?? ""} onChange={(v) => setDraft({ ...draft, brand: { ...draft.brand, name: v } })} />
                    <BrandField label="Tagline" value={draft.brand.tagline ?? ""} onChange={(v) => setDraft({ ...draft, brand: { ...draft.brand, tagline: v } })} />
                    <BrandField label="Mission" value={draft.brand.mission ?? ""} onChange={(v) => setDraft({ ...draft, brand: { ...draft.brand, mission: v } })} />
                    <BrandField label="URL" value={draft.brand.url ?? ""} onChange={(v) => setDraft({ ...draft, brand: { ...draft.brand, url: v } })} />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <BrandField label="Footer left (wordmark)" value={draft.footer.left} onChange={(v) => setDraft({ ...draft, footer: { ...draft.footer, left: v } })} />
                    <BrandField label="Footer right (handle)" value={draft.footer.right} onChange={(v) => setDraft({ ...draft, footer: { ...draft.footer, right: v } })} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="grid gap-3 p-6">
                  <div className="flex items-center justify-between">
                    <Label>Categories</Label>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setDraft({
                          ...draft,
                          categories: [...draft.categories, { name: "NEW", description: "" }],
                        })
                      }
                    >
                      <Plus className="size-4" /> Add
                    </Button>
                  </div>
                  {draft.categories.map((cat, i) => (
                    <div key={i} className="grid grid-cols-[1fr_1fr_100px_36px] gap-2 items-center">
                      <Input
                        value={cat.name}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            categories: draft.categories.map((c, j) => (j === i ? { ...c, name: e.target.value } : c)),
                          })
                        }
                      />
                      <Input
                        value={cat.description ?? ""}
                        placeholder="Description"
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            categories: draft.categories.map((c, j) => (j === i ? { ...c, description: e.target.value } : c)),
                          })
                        }
                      />
                      <Select
                        value={cat.ground ?? "none"}
                        onValueChange={(v) =>
                          setDraft({
                            ...draft,
                            categories: draft.categories.map((c, j) =>
                              j === i ? { ...c, ground: v === "none" ? undefined : v } : c
                            ),
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">no ground</SelectItem>
                          <SelectItem value="white">white</SelectItem>
                          <SelectItem value="black">black</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() =>
                          setDraft({ ...draft, categories: draft.categories.filter((_, j) => j !== i) })
                        }
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="grid gap-3 p-6">
                  <Label>Logo</Label>
                  {draft.has_logo ? (
                    <div className="flex items-center gap-3">
                      <img
                        src={`data:${draft.logo?.mime ?? "image/png"};base64,${draft.logo?.data ?? ""}`}
                        alt="logo"
                        className="h-16 w-auto border bg-white object-contain"
                      />
                      <Button variant="outline" size="sm" onClick={() => void handleRemoveLogo()}>
                        Remove
                      </Button>
                    </div>
                  ) : (
                    <Dropzone onFile={(f) => void handleLogo(f)} hint="Logo will appear in the logo slot of templates" />
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="tokens" className="grid gap-4">
              <Card>
                <CardContent className="grid gap-3 p-6">
                  {Object.entries(draft.tokens).map(([key, value]) => (
                    <div key={key} className="grid grid-cols-[1fr_1.5fr] items-center gap-3">
                      <Label className="font-mono text-xs">{key}</Label>
                      {COLOR_TOKENS.has(key) ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="color"
                            value={/^#[0-9a-fA-F]{6}$/.test(value) ? value : "#000000"}
                            onChange={(e) => setDraft({ ...draft, tokens: { ...draft.tokens, [key]: e.target.value } })}
                            className="size-8 cursor-pointer rounded border"
                          />
                          <Input
                            className="font-mono text-xs"
                            value={value}
                            onChange={(e) => setDraft({ ...draft, tokens: { ...draft.tokens, [key]: e.target.value } })}
                          />
                        </div>
                      ) : (
                        <Input
                          className="font-mono text-xs"
                          value={value}
                          onChange={(e) => setDraft({ ...draft, tokens: { ...draft.tokens, [key]: e.target.value } })}
                        />
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="campaigns" className="grid gap-4">
              <Card>
                <CardContent className="grid gap-4 p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-medium">Campaign presets</h3>
                      <p className="text-xs text-muted-foreground">
                        Tone, ground, and verbal language per post type.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setDraft({
                          ...draft,
                          campaigns: {
                            ...draft.campaigns,
                            [`campaign-${Object.keys(draft.campaigns).length + 1}`]: {
                              label: "New Campaign",
                              tone: "professional",
                              ground: "white",
                              language: "",
                            },
                          },
                        })
                      }
                    >
                      <Plus className="size-4" /> Add
                    </Button>
                  </div>
                  <div className="grid gap-1">
                    <div className="grid grid-cols-[120px_1fr_100px_1fr_36px] gap-2 px-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                      <span>Key</span>
                      <span>Label</span>
                      <span>Ground</span>
                      <span>Language</span>
                      <span />
                    </div>
                    {Object.entries(draft.campaigns).map(([key, c]) => (
                      <div
                        key={key}
                        className="grid grid-cols-[120px_1fr_100px_1fr_36px] items-center gap-2 rounded-md border px-1 py-1.5"
                      >
                        <span className="truncate px-1 font-mono text-xs">{key}</span>
                        <Input
                          value={c.label}
                          onChange={(e) =>
                            setDraft({ ...draft, campaigns: { ...draft.campaigns, [key]: { ...c, label: e.target.value } } })
                          }
                        />
                        <Select
                          value={c.ground}
                          onValueChange={(v) =>
                            setDraft({ ...draft, campaigns: { ...draft.campaigns, [key]: { ...c, ground: v } } })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="white">white</SelectItem>
                            <SelectItem value="black">black</SelectItem>
                          </SelectContent>
                        </Select>
                        <Input
                          value={c.language}
                          placeholder="Verbal language"
                          onChange={(e) =>
                            setDraft({ ...draft, campaigns: { ...draft.campaigns, [key]: { ...c, language: e.target.value } } })
                          }
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            const next = { ...draft.campaigns }
                            delete next[key]
                            setDraft({ ...draft, campaigns: next })
                          }}
                        >
                          <Trash2 className="size-4 text-destructive" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="advanced" className="grid gap-4">
              <TokenRolesEditor
                roles={draft.token_roles}
                onChange={(roles) => setDraft({ ...draft, token_roles: roles })}
              />
              <DesignInstructionEditor
                di={draft.design_instruction}
                onChange={(di) => setDraft({ ...draft, design_instruction: di })}
              />
            </TabsContent>

            <TabsContent value="preview">
              <DesignSystemPreview dsId={draft.id} />
            </TabsContent>
          </Tabs>
        </>
      )}

      <CreateFromInputDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        jobId={jobId}
        onJobStarted={setJobId}
        job={job}
        onDone={() => {
          setCreateOpen(false)
          setJobId(null)
          void mutate()
        }}
      />
    </div>
  )
}

function BrandField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

function TokenRolesEditor({
  roles,
  onChange,
}: {
  roles: Record<string, string>
  onChange: (roles: Record<string, string>) => void
}) {
  const entries = Object.entries(roles)
  return (
    <Card>
      <CardContent className="grid gap-3 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium">Token roles</h3>
            <p className="text-xs text-muted-foreground">
              Semantic descriptions the designer prompt sees for each CSS variable.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onChange({ ...roles, [`--color-${entries.length + 1}`]: "" })}
          >
            <Plus className="size-4" /> Add
          </Button>
        </div>
        <div className="grid gap-1">
          <div className="grid grid-cols-[1fr_1.5fr_36px] gap-2 px-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            <span>Variable</span>
            <span>Role</span>
            <span />
          </div>
          {entries.map(([key, role]) => (
            <div key={key} className="grid grid-cols-[1fr_1.5fr_36px] items-center gap-2 rounded-md border px-1 py-1.5">
              <Input
                className="font-mono text-xs"
                value={key}
                onChange={(e) => {
                  const newKey = e.target.value
                  const next: Record<string, string> = {}
                  for (const [k, v] of entries) {
                    next[k === key ? newKey : k] = k === key ? role : v
                  }
                  onChange(next)
                }}
              />
              <Input
                className="text-xs"
                value={role}
                placeholder="What this variable is for"
                onChange={(e) => onChange({ ...roles, [key]: e.target.value })}
              />
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  const next = { ...roles }
                  delete next[key]
                  onChange(next)
                }}
              >
                <Trash2 className="size-4 text-destructive" />
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

function ListEditor({
  title,
  items,
  onChange,
  placeholder,
}: {
  title: string
  items: string[]
  onChange: (items: string[]) => void
  placeholder: string
}) {
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h4>
        <Button variant="ghost" size="sm" onClick={() => onChange([...items, ""])}>
          <Plus className="size-3.5" /> Add
        </Button>
      </div>
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input
            value={item}
            placeholder={placeholder}
            onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))}
          />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onChange(items.filter((_, j) => j !== i))}
          >
            <Trash2 className="size-4 text-destructive" />
          </Button>
        </div>
      ))}
    </div>
  )
}

function DesignInstructionEditor({
  di,
  onChange,
}: {
  di: Record<string, unknown>
  onChange: (di: Record<string, unknown>) => void
}) {
  const style = (di.style as Record<string, unknown>) ?? {}
  const typeVoice = (di.type_voice as Record<string, string>) ?? {}
  const doDont = (di.do_dont as { do?: string[]; dont?: string[] }) ?? {}
  const doList = doDont.do ?? []
  const dontList = doDont.dont ?? []
  const allowed = Array.isArray(style.allowed_grounds) ? (style.allowed_grounds as string[]) : []

  function setStyle(patch: Record<string, unknown>) {
    onChange({ ...di, style: { ...style, ...patch } })
  }
  function setTypeVoice(patch: Record<string, string>) {
    onChange({ ...di, type_voice: { ...typeVoice, ...patch } })
  }
  function setDoDont(patch: { do?: string[]; dont?: string[] }) {
    onChange({ ...di, do_dont: { ...doDont, ...patch } })
  }

  return (
    <Card>
      <CardContent className="grid gap-5 p-6">
        <div className="grid gap-2">
          <h3 className="text-sm font-medium">Design instruction</h3>
          <p className="text-xs text-muted-foreground">
            The Swiss-style rules the designer and verifier audit against.
          </p>
        </div>

        <div className="grid gap-3">
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Style</h4>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label className="text-xs">System name</Label>
              <Input
                value={String(style.name ?? "")}
                onChange={(e) => setStyle({ name: e.target.value })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Palette</Label>
              <Input
                value={String(style.palette ?? "")}
                onChange={(e) => setStyle({ palette: e.target.value })}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-xs text-muted-foreground">Allowed grounds:</span>
            {(["white", "black"] as const).map((g) => (
              <label key={g} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={allowed.includes(g)}
                  onChange={(e) => {
                    const next = e.target.checked
                      ? [...allowed, g]
                      : allowed.filter((x) => x !== g)
                    setStyle({ allowed_grounds: next })
                  }}
                />
                {g}
              </label>
            ))}
            <div className="ml-2 flex flex-wrap items-center gap-4">
              <Toggle
                label="shadows"
                checked={Boolean(style.shadows)}
                onChange={(v) => setStyle({ shadows: v })}
              />
              <Toggle
                label="gradients"
                checked={Boolean(style.gradients)}
                onChange={(v) => setStyle({ gradients: v })}
              />
              <Toggle
                label="illustrations"
                checked={Boolean(style.illustrations)}
                onChange={(v) => setStyle({ illustrations: v })}
              />
              <Toggle
                label="icons"
                checked={Boolean(style.icons)}
                onChange={(v) => setStyle({ icons: v })}
              />
            </div>
          </div>
        </div>

        <div className="grid gap-3">
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Type voice</h4>
          <div className="grid gap-3">
            {(["display", "serif", "body"] as const).map((voice) => (
              <div key={voice} className="grid gap-1.5">
                <Label className="text-xs uppercase">{voice}</Label>
                <Textarea
                  value={typeVoice[voice] ?? ""}
                  onChange={(e) => setTypeVoice({ [voice]: e.target.value })}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ListEditor
            title="Do"
            items={doList}
            onChange={(doItems) => setDoDont({ do: doItems })}
            placeholder="A rule to always follow"
          />
          <ListEditor
            title="Don't"
            items={dontList}
            onChange={(dontItems) => setDoDont({ dont: dontItems })}
            placeholder="A rule to never break"
          />
        </div>
      </CardContent>
    </Card>
  )
}

function DesignSystemPreview({ dsId }: { dsId: string }) {
  const [html, setHtml] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    setHtml(null)
    import("@/lib/api").then(({ apiRequest }) =>
      apiRequest<{ html: string }>(`/design-systems/${dsId}/preview`, { method: "POST" })
        .then((r) => {
          if (alive) setHtml(r.html)
        })
        .catch(() => {
          if (alive) setHtml("")
        })
    )
    return () => {
      alive = false
    }
  }, [dsId])
  if (html === null) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }
  return (
    <Card>
      <CardContent className="grid gap-3 p-6">
        <p className="text-sm text-muted-foreground">
          Sample post rendered with this design system's tokens, fonts, and logo.
        </p>
        {html ? (
          <div className="flex justify-center">
            <ScaledFrame html={html} width={1080} height={1080} maxWidth={640} maxHeight={640} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Preview unavailable.</p>
        )}
      </CardContent>
    </Card>
  )
}

function CreateFromInputDialog({
  open,
  onOpenChange,
  jobId,
  onJobStarted,
  job,
  onDone,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  jobId: string | null
  onJobStarted: (id: string) => void
  job: ReturnType<typeof useAgentJob>["data"]
  onDone: () => void
}) {
  const [form, setForm] = useState({
    name: "",
    tagline: "",
    mission: "",
    industry: "",
    audience: "",
    style: "",
    handle: "",
  })
  const [reference, setReference] = useState<File | null>(null)
  const [logo, setLogo] = useState<File | null>(null)
  const [starting, setStarting] = useState(false)

  function set(field: keyof typeof form) {
    return (v: string) => setForm((prev) => ({ ...prev, [field]: v }))
  }

  async function start() {
    if (!form.name.trim()) {
      toast.error("Brand name is required")
      return
    }
    setStarting(true)
    try {
      const res = await createDesignSystemFromInput({
        ...form,
        referenceImage: reference,
        logoImage: logo,
      })
      onJobStarted(res.job_id)
      toast.success("Design system job started")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Start failed")
    } finally {
      setStarting(false)
    }
  }

  const done = isJobDone(job)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Create Design System with AI</DialogTitle>
          <DialogDescription>
            The brand builder generates identity, tokens, campaigns, and starter templates.
          </DialogDescription>
        </DialogHeader>
        {jobId ? (
          <div className="grid gap-2">
            <p className="text-sm">
              Job status:{" "}
              <Badge variant={job?.status === "completed" ? "default" : "outline"}>
                {job?.status ?? "starting"}
              </Badge>
            </p>
            {job?.status === "completed" ? (
              <p className="text-sm text-muted-foreground">
                Created: <code>{(job.result as { design_system_id?: string })?.design_system_id}</code>
                {" · "}
                {((job.result as { templates?: string[] })?.templates ?? []).length} templates
              </p>
            ) : null}
            {job?.status === "failed" ? <p className="text-sm text-destructive">{job.error}</p> : null}
            {done ? (
              <Button onClick={onDone}>Done</Button>
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Building brand system…
              </p>
            )}
          </div>
        ) : (
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-3">
              <Input placeholder="Brand name *" value={form.name} onChange={(e) => set("name")(e.target.value)} />
              <Input placeholder="Handle (e.g. @sapienskid)" value={form.handle} onChange={(e) => set("handle")(e.target.value)} />
            </div>
            <Input placeholder="Tagline" value={form.tagline} onChange={(e) => set("tagline")(e.target.value)} />
            <Textarea
              placeholder="Mission / brand story"
              value={form.mission}
              onChange={(e) => set("mission")(e.target.value)}
            />
            <div className="grid grid-cols-3 gap-3">
              <Input placeholder="Industry" value={form.industry} onChange={(e) => set("industry")(e.target.value)} />
              <Input placeholder="Audience" value={form.audience} onChange={(e) => set("audience")(e.target.value)} />
              <Input placeholder="Style keywords" value={form.style} onChange={(e) => set("style")(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1">
                <Label className="text-xs text-muted-foreground">Reference / moodboard (optional)</Label>
                {reference ? (
                  <div className="flex items-center justify-between rounded-md border p-2 text-sm">
                    <span className="truncate">{reference.name}</span>
                    <Button variant="ghost" size="sm" onClick={() => setReference(null)}>
                      Remove
                    </Button>
                  </div>
                ) : (
                  <Dropzone onFile={setReference} hint="Palette + type inspiration" />
                )}
              </div>
              <div className="grid gap-1">
                <Label className="text-xs text-muted-foreground">Logo (optional)</Label>
                {logo ? (
                  <div className="flex items-center justify-between rounded-md border p-2 text-sm">
                    <span className="truncate">{logo.name}</span>
                    <Button variant="ghost" size="sm" onClick={() => setLogo(null)}>
                      Remove
                    </Button>
                  </div>
                ) : (
                  <Dropzone onFile={setLogo} hint="Used in template logo slots" />
                )}
              </div>
            </div>
          </div>
        )}
        <DialogFooter>
          {!jobId ? (
            <Button onClick={() => void start()} disabled={starting}>
              {starting ? (
                <>
                  <Loader2 className="size-4 animate-spin" /> Starting…
                </>
              ) : (
                <>
                  <Wand2 className="size-4" /> Generate
                </>
              )}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
