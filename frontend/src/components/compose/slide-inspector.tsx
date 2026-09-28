import { useEffect, useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { ComposeGround, Template } from "@/lib/api"
import { MediaPicker } from "./media-picker"
import { TemplatePicker } from "./template-picker"
import { TextFields } from "./text-fields"
import { templateFields, templateHasMedia, templateMediaKinds, type EditorSlide } from "./model"

type Tab = "template" | "text" | "media"

/**
 * Right-hand inspector for the selected slide: Template (gallery + element
 * toggles), Text (template-declared fields only) and Media (if supported).
 */
export function SlideInspector({
  slide,
  family,
  orientation,
  templates,
  templatesLoading,
  ground,
  multiSlide,
  onChange,
  onApplyTemplate,
  onApplyMedia,
}: {
  slide: EditorSlide
  family: string
  orientation: "square" | "portrait" | "landscape"
  templates: Template[]
  templatesLoading: boolean
  ground: ComposeGround
  multiSlide: boolean
  onChange: (patch: Partial<EditorSlide>) => void
  onApplyTemplate: (scope: "post" | "all") => void
  onApplyMedia: (scope: "post" | "all") => void
}) {
  const template = templates.find((t) => t.id === slide.template_id)
  const hasMedia = templateHasMedia(template)
  const [tab, setTab] = useState<Tab>(slide.template_id ? "text" : "template")

  // Leaving a media-capable template while on the Media tab → fall back.
  useEffect(() => {
    if (tab === "media" && !hasMedia) setTab("text")
  }, [tab, hasMedia])

  const fields = templateFields(template)
  const fallback = !template?.fields || template.fields.length === 0
  const hidden = slide.hidden ?? template?.hidden_elements ?? []

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="gap-3">
      <TabsList className="w-full">
        <TabsTrigger value="template">Template</TabsTrigger>
        <TabsTrigger value="text" disabled={!slide.template_id}>
          Text
        </TabsTrigger>
        <TabsTrigger value="media" disabled={!hasMedia} title={hasMedia ? undefined : "This template has no media slot"}>
          Media
        </TabsTrigger>
      </TabsList>
      <TabsContent value="template">
        <TemplatePicker
          family={family}
          templates={templates}
          loading={templatesLoading}
          selected={template}
          ground={ground}
          hidden={slide.hidden}
          mediaPosition={slide.media_position}
          multiSlide={multiSlide}
          onPick={(id) => onChange({ template_id: id, hidden: null })}
          onHidden={(h) => onChange({ hidden: h })}
          onMediaPosition={(p) => onChange({ media_position: p })}
          onApplyAll={onApplyTemplate}
        />
      </TabsContent>
      <TabsContent value="text">
        {template ? (
          <TextFields
            fields={fields}
            copy={slide.copy}
            hidden={hidden}
            fallback={fallback}
            onChange={(copy) => onChange({ copy })}
          />
        ) : (
          <p className="text-xs text-muted-foreground">Choose a template first.</p>
        )}
      </TabsContent>
      <TabsContent value="media">
        {hasMedia ? (
          <MediaPicker
            media={slide.media}
            mediaKinds={templateMediaKinds(template)}
            ground={ground}
            orientation={orientation}
            multiSlide={multiSlide}
            onChange={(media) => onChange({ media })}
            onApplyAll={onApplyMedia}
          />
        ) : null}
      </TabsContent>
    </Tabs>
  )
}
