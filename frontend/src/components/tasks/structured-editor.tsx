import { useEffect, useMemo, useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TemplatePicker } from "@/components/compose/template-picker"
import { TextFields } from "@/components/compose/text-fields"
import { MediaPicker } from "@/components/compose/media-picker"
import {
  ALL_FIELDS,
  FALLBACK_FIELDS,
  getField,
  isFieldKey,
  setField,
  templateFields,
  templateHasMedia,
  templateMediaKinds,
  emptyCopy,
  type FieldKey,
} from "@/components/compose/model"
import { useEditorDoc } from "@/hooks/use-editor-session"
import { useTemplates } from "@/hooks/use-library"
import type { EditorSession } from "@/lib/editor-session"
import type { MediaChoice } from "@/lib/editor-store"
import type {
  ComposeCopy,
  ComposeMedia,
  ComposeMediaPosition,
  EditorState,
} from "@/lib/api"

/** Rendered slots → form copy (extra.* keys map into copy.extra). */
function copyFromSlots(slots: Readonly<Record<string, string>>): ComposeCopy {
  let copy = emptyCopy()
  for (const [k, v] of Object.entries(slots)) {
    if (isFieldKey(k)) copy = setField(copy, k, v)
  }
  return copy
}

function isComplete(m: ComposeMedia): m is MediaChoice {
  if (m.kind === "none") return false
  if (m.kind === "upload") return !!m.data
  if (m.kind === "photo") return !!m.url
  return true
}

/**
 * Compose-parity inspector for a template-built post. Every control writes
 * into the session's shared store: text is patched into the preview in the
 * same frame, structural changes update optimistically and fetch a fast
 * server preview, and a coalesced background save persists it all.
 */
export function StructuredEditor({
  session,
  info,
}: {
  session: EditorSession
  info: EditorState
}) {
  const doc = useEditorDoc(session)
  const store = session.store
  const [tab, setTab] = useState<"template" | "text" | "media">("text")
  const { data: templates, isLoading } = useTemplates(info.design_system_id, info.family)
  const selected = (templates ?? []).find((t) => t.id === doc.templateId)

  // Template default toggles feed the request builder (explicit hidden lists).
  useEffect(() => {
    session.defaultHidden = (id) => (templates ?? []).find((t) => t.id === id)?.hidden_elements
  }, [session, templates])

  const { fields, fallback } = useMemo<{ fields: FieldKey[]; fallback: boolean }>(() => {
    const fromTemplate = selected ? templateFields(selected) : []
    if (fromTemplate.length > 0 && selected?.fields?.length) return { fields: fromTemplate, fallback: false }
    const fromSlots = Object.keys(doc.slots).filter(isFieldKey)
    if (fromSlots.length > 0) return { fields: ALL_FIELDS.filter((f) => fromSlots.includes(f)), fallback: false }
    return { fields: [...FALLBACK_FIELDS], fallback: true }
  }, [selected, doc.slots])

  const copy = useMemo(() => copyFromSlots(doc.slots), [doc.slots])

  function handleCopy(next: ComposeCopy) {
    for (const f of ALL_FIELDS) {
      const v = getField(next, f)
      if (v !== getField(copy, f)) store.setSlot(f, v, "form")
    }
  }

  const hasMedia = templateHasMedia(selected)
  const mediaKinds = selected ? templateMediaKinds(selected) : info.media_kinds
  const orientation =
    info.family === "landscape" ? "landscape" : info.family === "square" ? "square" : "portrait"
  const [picker, setPicker] = useState<ComposeMedia>({ kind: "none" })
  const shownMedia: ComposeMedia = doc.media ?? (picker.kind !== "none" ? picker : { kind: "none" })

  function handleMedia(m: ComposeMedia) {
    setPicker(m)
    if (isComplete(m)) store.setMedia(m, m.kind === "upload")
  }

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as "template" | "text" | "media")} className="gap-3">
      <TabsList className="w-full">
        <TabsTrigger value="template">Template</TabsTrigger>
        <TabsTrigger value="text">Text</TabsTrigger>
        <TabsTrigger value="media" disabled={!hasMedia && !templates} title={hasMedia ? undefined : "This template has no media slot"}>
          Media
        </TabsTrigger>
      </TabsList>

      <TabsContent value="template">
        <TemplatePicker
          family={info.family}
          templates={templates ?? []}
          loading={isLoading}
          selected={selected}
          ground={info.ground}
          hidden={doc.hidden ? [...doc.hidden] : null}
          mediaPosition={doc.mediaPosition as ComposeMediaPosition}
          multiSlide={false}
          showApplyAll={false}
          onPick={(id) => store.setTemplate(id)}
          onHidden={(h) => store.setHidden(h)}
          onMediaPosition={(p) => store.setMediaPosition(p)}
          onApplyAll={() => {}}
        />
      </TabsContent>

      <TabsContent value="text" className="grid gap-3">
        <TextFields
          fields={fields}
          copy={copy}
          hidden={doc.hidden ? [...doc.hidden] : (selected?.hidden_elements ?? [])}
          fallback={fallback}
          onChange={handleCopy}
        />
        <p className="text-[11px] text-muted-foreground">
          Edits appear instantly and save automatically.
        </p>
      </TabsContent>

      <TabsContent value="media" className="grid gap-3">
        {!hasMedia ? (
          <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
            This template has no media slot.
          </p>
        ) : (
          <>
            <p className="text-[11px] text-muted-foreground">
              Current media stays until you pick a replacement — it applies instantly.
            </p>
            <MediaPicker
              media={shownMedia}
              mediaKinds={mediaKinds}
              ground={info.ground}
              orientation={orientation}
              multiSlide={false}
              onChange={handleMedia}
              onApplyAll={() => {}}
              hideApply
            />
          </>
        )}
      </TabsContent>
    </Tabs>
  )
}
