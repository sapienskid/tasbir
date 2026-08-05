import { useEffect, useId, useMemo, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { ArrowLeft, Loader2, Plus, RefreshCw, Save, Search, Trash2, Wand2 } from "lucide-react"
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
import { FontPickerDialog } from "@/components/design-system/font-picker"
import { ZoomableFrame } from "@/components/tasks/preview-frame"
import {
  applyStyleLanguage,
  createDesignLanguage,
  createDesignSystem,
  createDesignSystemFromInput,
  deleteDesignLanguage,
  deleteDesignSystem,
  getDesignSystem,
  listDesignLanguages,
  listStyleLanguages,
  removeLogo,
  updateDesignSystem,
  uploadLogo,
  type DesignLanguage,
  type DesignSystem,
  type StyleLanguage,
} from "@/lib/api"
import { useDesignSystems } from "@/hooks/use-library"

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

const FONT_TOKENS = new Set(["--font-sans", "--font-display", "--font-serif"])

// Each font role's picker is restricted to its matching type — except the
// headline role, which may be any kind of typeface.
const FONT_TOKEN_CATEGORIES: Record<string, string[] | undefined> = {
  "--font-sans": ["sans-serif"],
  "--font-serif": ["serif"],
  "--font-display": undefined,
}

// Human-friendly labels so users see "color-bg" instead of raw CSS variables.
const TOKEN_LABELS: Record<string, string> = {
  "--color-bg": "Background",
  "--color-bg-inverted": "Background (inverted)",
  "--color-text": "Text",
  "--color-text-inverted": "Text (inverted)",
  "--color-text-secondary": "Text (secondary)",
  "--color-text-tertiary": "Text (tertiary)",
  "--color-border": "Border",
  "--color-border-inverted": "Border (inverted)",
  "--color-accent": "Accent",
  "--font-sans": "Sans — body & interface",
  "--font-display": "Headline — any typeface",
  "--font-serif": "Serif — subhead & body",
  "--radius-sm": "Radius (small)",
  "--radius-md": "Radius (medium)",
  "--shadow-md": "Shadow",
}

function tokenLabel(key: string): string {
  return TOKEN_LABELS[key] ?? key.replace(/^--/, "")
}

function firstFamily(stack: string): string {
  return stack.split(/[,'"]/)[0].trim()
}

export default function DesignSystemsPage() {
  const { data: systems, isLoading, mutate } = useDesignSystems()
  const [draft, setDraft] = useState<DesignSystem | null>(null)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [newOpen, setNewOpen] = useState(false)
  const [newMode, setNewMode] = useState<"blank" | "ai">("blank")
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")
  const [creatingNew, setCreatingNew] = useState(false)
  const [fontPickerKey, setFontPickerKey] = useState<string | null>(null)
  const [styles, setStyles] = useState<StyleLanguage[]>([])
  const [applyingStyle, setApplyingStyle] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [langOpen, setLangOpen] = useState(false)
  const [langs, setLangs] = useState<DesignLanguage[]>([])
  const [langNewName, setLangNewName] = useState("")
  const [langBase, setLangBase] = useState("")
  const [langCreating, setLangCreating] = useState(false)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [dsId, setDsId] = useState<string>(() => searchParams.get("ds") ?? "")

  useEffect(() => {
    listStyleLanguages()
      .then(setStyles)
      .catch(() => setStyles([]))
  }, [])

  function applyFontFamily(key: string, family: string) {
    setDraft((prev) => {
      if (!prev) return prev
      const current = prev.tokens[key] ?? ""
      const rest = current.includes(",") ? current.slice(current.indexOf(",")) : ""
      return { ...prev, tokens: { ...prev.tokens, [key]: family + rest } }
    })
  }

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

  const currentStyle = useMemo(
    () =>
      styles.find(
        (s) => s.id === (draft?.design_instruction?.style_language ?? "")
      ) ?? null,
    [styles, draft]
  )

  async function handleApplyStyle(lang: string) {
    if (!draft) return
    if (lang === currentStyle?.id) {
      toast.info(`${currentStyle?.label ?? lang} is already active`)
      return
    }
    const chosen = styles.find((s) => s.id === lang) ?? null
    setApplyingStyle(true)

    // Optimistic update — reflect the choice instantly so the UI never looks
    // frozen, even before the round-trip returns.
    setDraft((prev) => {
      if (!prev) return prev
      const di = prev.design_instruction ?? {}
      const style: Record<string, unknown> = { ...((di.style ?? {}) as Record<string, unknown>) }
      if (chosen) {
        style.name = chosen.label
        style.emoji = chosen.emoji
        style.accent = chosen.accent ? "accent" : "none"
      }
      const nextTokens = { ...(prev.tokens ?? {}) }
      // Apply the style's core palette + accent tokens so the Tokens tab and
      // any preview change the moment the language is picked.
      for (const [key, value] of Object.entries(chosen?.palette_tokens ?? {})) {
        nextTokens[key] = value
      }
      delete nextTokens["--color-accent"]
      delete nextTokens["--color-accent-secondary"]
      if (chosen) Object.assign(nextTokens, chosen.accent_tokens)
      return {
        ...prev,
        design_instruction: { ...di, style_language: lang, style },
        tokens: nextTokens,
      }
    })

    try {
      const fresh = await applyStyleLanguage(draft.id, lang)
      setDraft(structuredClone(fresh))
      void mutate()
      const seeded = fresh.seeded_templates?.length ?? 0
      const bits: string[] = []
      if (chosen) {
        bits.push(chosen.emoji ? "emoji allowed" : "no emoji")
        bits.push(chosen.grayscale ? "photos grayscale" : "photos full color")
        const accentCount = Object.keys(chosen.accent_tokens ?? {}).length
        if (accentCount) bits.push(`${accentCount} accent token(s)`)
      }
      if (seeded) bits.push(`${seeded} starter template(s)`)
      toast.success(
        `Applied ${chosen?.label ?? lang}${bits.length ? ` — ${bits.join(", ")}` : ""}`
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not apply style")
      // Roll the optimistic change back to server truth so nothing lingers.
      try {
        const truth = await getDesignSystem(draft.id)
        setDraft(structuredClone(truth))
      } catch {
        /* keep optimistic state; server may be unreachable */
      }
    } finally {
      setApplyingStyle(false)
    }
  }

  async function retryStyles() {
    try {
      setStyles(await listStyleLanguages())
    } catch {
      toast.error("Could not load design languages")
    }
  }

  async function openLangManager() {
    setLangOpen(true)
    try {
      setLangs(await listDesignLanguages())
    } catch {
      toast.error("Could not load design languages")
    }
  }

  async function handleCreateLang() {
    const name = langNewName.trim()
    if (!name || !langBase) return
    setLangCreating(true)
    try {
      await createDesignLanguage(name, langBase)
      setLangNewName("")
      setLangs(await listDesignLanguages())
      setStyles(await listStyleLanguages())
      toast.success(`Created design language ${name}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create design language")
    } finally {
      setLangCreating(false)
    }
  }

  async function handleDeleteLang(id: string) {
    try {
      await deleteDesignLanguage(id)
      setLangs(await listDesignLanguages())
      setStyles(await listStyleLanguages())
      toast.success("Design language deleted")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete design language")
    }
  }

  async function handleDelete() {
    if (!draft) return
    try {
      await deleteDesignSystem(draft.id)
      toast.success(`Deleted ${draft.name}`)
      setDeleteOpen(false)
      setDraft(null)
      setDsId("")
      void mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete design system")
      setDeleteOpen(false)
    }
  }

  async function handleCreateNew() {
    const name = newName.trim()
    if (!name) return
    setCreatingNew(true)
    try {
      const created = await createDesignSystem(name, newDesc.trim())
      setNewOpen(false)
      setNewName("")
      setNewDesc("")
      setDsId(created.id)
      void mutate()
      toast.success(`Created ${created.name} — now pick a design language`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create design system")
    } finally {
      setCreatingNew(false)
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
          No design systems yet — create one (blank or with the AI brand builder).
        </p>
        <div>
          <Button onClick={() => setNewOpen(true)}>
            <Plus aria-hidden="true" className="size-4" />
            New design system
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
              <ArrowLeft aria-hidden="true" className="size-4" />
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
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Design system
            </span>
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
          </div>
          <Button variant="outline" onClick={() => setNewOpen(true)}>
            <Plus aria-hidden="true" className="size-4" />
            New design system
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
            <div className="flex items-center gap-2">
              <Button onClick={() => void save()} disabled={saving}>
                {saving ? (
                  <>
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Saving…
                  </>
                ) : (
                  <>
                    <Save aria-hidden="true" className="size-4" /> Save
                  </>
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Delete design system"
                title={draft.id === "default" ? "The default design system cannot be deleted" : "Delete this design system"}
                onClick={() => {
                  if (draft.id === "default") {
                    toast.info("The default design system cannot be deleted")
                    return
                  }
                  setDeleteOpen(true)
                }}
              >
                <Trash2 aria-hidden="true" className="size-4 text-destructive" />
              </Button>
            </div>
          </div>

          <Card>
            <CardContent className="flex flex-wrap items-center gap-4 p-4">
              <div className="flex items-center gap-3">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Design language
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => {
                    setLangNewName("")
                    setLangBase("")
                    void openLangManager()
                  }}
                >
                  <Plus aria-hidden="true" className="size-3.5" />
                  New
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => void openLangManager()}
                >
                  Manage
                </Button>
                <Select
                  value={currentStyle?.id ?? ""}
                  onValueChange={(v) => void handleApplyStyle(v)}
                  disabled={applyingStyle}
                >
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Select a design language" />
                  </SelectTrigger>
                  <SelectContent>
                    {styles.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {styles.length === 0 && (
                  <Button
                    variant="outline"
                    size="icon"
                    aria-label="Reload design languages"
                    onClick={() => void retryStyles()}
                  >
                    <RefreshCw aria-hidden="true" className="size-4" />
                  </Button>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {currentStyle?.label ?? "No design language selected"}
                </p>                <p className="text-xs text-muted-foreground">
                  {currentStyle
                    ? `${currentStyle.description} ${
                        currentStyle.emoji ? "Emoji allowed. " : "No emoji. "
                      }${
                        currentStyle.grayscale ? "Photos render grayscale." : "Photos render full color."
                      }`
                    : "A design language is the visual style preset applied to THIS design system (its palette rules, type mood, decoration, media). It is a setting of the design system — not a separate design system. You can switch it anytime."}
                </p>
                {currentStyle && (
                  <div className="mt-2 flex items-center gap-1.5">
                    {Object.entries({ ...currentStyle.palette_tokens, ...currentStyle.accent_tokens })
                      .filter(([k]) => k.startsWith("--color") && !k.endsWith("inverted"))
                      .map(([k, v]) => (
                        <span
                          key={k}
                          title={`${k}: ${v}`}
                          className="size-5 rounded-full border"
                          style={{ backgroundColor: v }}
                        />
                      ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

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
                      <Plus aria-hidden="true" className="size-4" /> Add
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
                        aria-label="Delete category"
                        onClick={() =>
                          setDraft({ ...draft, categories: draft.categories.filter((_, j) => j !== i) })
                        }
                      >
                        <Trash2 aria-hidden="true" className="size-4 text-destructive" />
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
                        width={64}
                        height={64}
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
                  <p className="text-xs text-muted-foreground">
                    Design tokens — CSS variables resolved at render time. Fonts load from Google
                    Fonts automatically; the first family in each stack is what renders.
                  </p>
                  {Object.entries(draft.tokens).map(([key, value]) => (
                    <div key={key} className="grid grid-cols-[1fr_1.5fr] items-center gap-3">
                      <div className="grid gap-0.5">
                        <Label className="text-xs">{tokenLabel(key)}</Label>
                        <span className="font-mono text-[10px] text-muted-foreground">{key}</span>
                      </div>
                      {COLOR_TOKENS.has(key) ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="color"
                            aria-label={`${tokenLabel(key)} color`}
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
                      ) : FONT_TOKENS.has(key) ? (
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            className="justify-between gap-2 font-mono text-xs"
                            onClick={() => setFontPickerKey(key)}
                            title="Search Google Fonts"
                          >
                            <span className="max-w-40 truncate">{firstFamily(value) || "—"}</span>
                            <Search aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground" />
                          </Button>
                          <Input
                            className="font-mono text-xs"
                            value={value}
                            placeholder="Family, fallback, sans-serif"
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
              <FontPickerDialog
                open={fontPickerKey !== null}
                onOpenChange={(o) => !o && setFontPickerKey(null)}
                currentFamily={fontPickerKey ? firstFamily(draft.tokens[fontPickerKey] ?? "") : ""}
                onPick={(family) => fontPickerKey && applyFontFamily(fontPickerKey, family)}
                categories={fontPickerKey ? FONT_TOKEN_CATEGORIES[fontPickerKey] : undefined}
              />
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
                      <Plus aria-hidden="true" className="size-4" /> Add
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
                          aria-label="Delete campaign"
                          onClick={() => {
                            const next = { ...draft.campaigns }
                            delete next[key]
                            setDraft({ ...draft, campaigns: next })
                          }}
                        >
                          <Trash2 aria-hidden="true" className="size-4 text-destructive" />
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
        onJobStarted={(jobId) => {
          setCreateOpen(false)
          navigate(`/jobs/${jobId}`)
        }}
      />

      {draft && (
        <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete design system</DialogTitle>
              <DialogDescription>
                This permanently deletes <span className="font-medium">{draft.name}</span>{" "}
                and all of its templates. This cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteOpen(false)}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={() => void handleDelete()}>
                <Trash2 aria-hidden="true" className="size-4" /> Delete
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New design system</DialogTitle>
            <DialogDescription>
              A design system is a brand's identity (name, tokens, categories, campaigns)
              plus the design language that styles its posts.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setNewMode("blank")}
              className={`rounded-md border p-3 text-left transition-colors ${
                newMode === "blank" ? "border-primary bg-primary/5" : "hover:bg-muted"
              }`}
            >
              <p className="text-sm font-medium">Blank system</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Creates an empty brand shell (Swiss by default). You fill in the
                identity, tokens, and pick a design language yourself.
              </p>
            </button>
            <button
              type="button"
              onClick={() => setNewMode("ai")}
              className={`rounded-md border p-3 text-left transition-colors ${
                newMode === "ai" ? "border-primary bg-primary/5" : "hover:bg-muted"
              }`}
            >
              <p className="text-sm font-medium">Generate with AI</p>
              <p className="mt-1 text-xs text-muted-foreground">
                The brand builder designs a complete system for you from a few
                fields and optional reference/logo images.
              </p>
            </button>
          </div>

          {newMode === "blank" ? (
            <div className="grid gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="new-ds-name">Name</Label>
                <Input
                  id="new-ds-name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Acme"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleCreateNew()
                  }}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="new-ds-desc">Description (optional)</Label>
                <Textarea
                  id="new-ds-desc"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  rows={2}
                />
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              You'll be asked for a name, industry, audience, handle, and optional
              reference / logo images. The AI builds the brand, tokens, campaigns,
              and starter templates. Runs as a background job.
            </p>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setNewOpen(false)}>
              Cancel
            </Button>
            {newMode === "blank" ? (
              <Button onClick={() => void handleCreateNew()} disabled={creatingNew || !newName.trim()}>
                {creatingNew ? (
                  <>
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Creating…
                  </>
                ) : (
                  "Create"
                )}
              </Button>
            ) : (
              <Button
                onClick={() => {
                  setNewOpen(false)
                  setCreateOpen(true)
                }}
              >
                <Wand2 aria-hidden="true" className="size-4" />
                Open AI brand builder
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={langOpen} onOpenChange={setLangOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Design languages</DialogTitle>
            <DialogDescription>
              A design language is a reusable visual style bundle. Built-in languages
              can't be deleted; you can add custom ones based on any language.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-2">
            {langs.map((l) => {
              const builtIn = styles.some((s) => s.id === l.id && s.label === l.name)
              return (
                <div key={l.id} className="flex items-center justify-between rounded-md border p-2.5">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{l.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {l.id} · {l.emoji ? "emoji" : "no emoji"} ·{" "}
                      {l.grayscale ? "grayscale" : "color"} photos
                    </p>
                  </div>
                  {!builtIn ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete ${l.name}`}
                      onClick={() => void handleDeleteLang(l.id)}
                    >
                      <Trash2 aria-hidden="true" className="size-4 text-destructive" />
                    </Button>
                  ) : (
                    <Badge variant="outline">built-in</Badge>
                  )}
                </div>
              )
            })}
          </div>

          <div className="grid gap-2 border-t pt-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              New custom language
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Input
                value={langNewName}
                onChange={(e) => setLangNewName(e.target.value)}
                placeholder="Name (e.g. Warm Editorial)"
              />
              <Select value={langBase} onValueChange={setLangBase}>
                <SelectTrigger>
                  <SelectValue placeholder="Based on…" />
                </SelectTrigger>
                <SelectContent>
                  {styles.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => void handleCreateLang()}
              disabled={langCreating || !langNewName.trim() || !langBase}
            >
              {langCreating ? (
                <>
                  <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Creating…
                </>
              ) : (
                "Create language"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
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
  const id = useId()
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} value={value} onChange={(e) => onChange(e.target.value)} />
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
            <Plus aria-hidden="true" className="size-4" /> Add
          </Button>
        </div>
        <div className="grid gap-1">
          <div className="grid grid-cols-[1fr_1.5fr_36px] gap-2 px-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            <span>Variable</span>
            <span>Role</span>
            <span />
          </div>
          {entries.map(([key, role]) => (
            <div key={key} className="grid gap-1 rounded-md border px-1.5 py-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium">{tokenLabel(key)}</span>
                <span className="font-mono text-[10px] text-muted-foreground">{key}</span>
              </div>
              <div className="grid grid-cols-[1fr_1.5fr_36px] items-center gap-2">
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
                  aria-label="Delete role"
                  onClick={() => {
                    const next = { ...roles }
                    delete next[key]
                    onChange(next)
                  }}
                >
                  <Trash2 aria-hidden="true" className="size-4 text-destructive" />
                </Button>
              </div>
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
          <Plus aria-hidden="true" className="size-3.5" /> Add
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
            aria-label="Remove item"
            onClick={() => onChange(items.filter((_, j) => j !== i))}
          >
            <Trash2 aria-hidden="true" className="size-4 text-destructive" />
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
        <Loader2 aria-hidden="true" className="size-5 animate-spin text-muted-foreground" />
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
          <div className="h-[560px] rounded-md border bg-muted/10">
            <ZoomableFrame html={html} width={1080} height={1080} />
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
  onJobStarted,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onJobStarted: (jobId: string) => void
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
      toast.success("Brand builder job started")
      onJobStarted(res.job_id)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Start failed")
    } finally {
      setStarting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Create Design System with AI</DialogTitle>
          <DialogDescription>
            The brand builder generates identity, tokens, campaigns, and starter
            templates in the background. The job keeps running if you close this
            — find it on the Tasks page.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="Brand name *" aria-label="Brand name" value={form.name} onChange={(e) => set("name")(e.target.value)} />
            <Input placeholder="Handle (e.g. @sapienskid)" aria-label="Handle" value={form.handle} onChange={(e) => set("handle")(e.target.value)} />
          </div>
          <Input placeholder="Tagline" aria-label="Tagline" value={form.tagline} onChange={(e) => set("tagline")(e.target.value)} />
          <Textarea
            placeholder="Mission / brand story"
            aria-label="Mission / brand story"
            value={form.mission}
            onChange={(e) => set("mission")(e.target.value)}
          />
          <div className="grid grid-cols-3 gap-3">
            <Input placeholder="Industry" aria-label="Industry" value={form.industry} onChange={(e) => set("industry")(e.target.value)} />
            <Input placeholder="Audience" aria-label="Audience" value={form.audience} onChange={(e) => set("audience")(e.target.value)} />
            <Input placeholder="Style keywords" aria-label="Style keywords" value={form.style} onChange={(e) => set("style")(e.target.value)} />
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
        <DialogFooter>
          <Button onClick={() => void start()} disabled={starting}>
            {starting ? (
              <>
                <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Starting…
              </>
            ) : (
              <>
                <Wand2 aria-hidden="true" className="size-4" /> Generate
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
