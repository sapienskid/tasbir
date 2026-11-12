import { apiRequest } from "@/lib/api"

export interface CoverSettings {
  design_system_id: string
  title: string
  content: string
  theme: string
  engine: "procedural" | "ai"
  motif: string
  ground: "white" | "black"
  placement: "center" | "left" | "right"
  texture: "clean" | "print"
  variations: number
  seed: string
  width: number
  height: number
}

export interface CoverMeta {
  width: number
  height: number
  motifs: { id: string; label: string }[]
  concepts?: { id: string; label: string }[]
  sizes: { label: string; width: number; height: number }[]
  ai_available: boolean
}

export const DEFAULT_COVER: CoverSettings = {
  design_system_id: "", title: "", content: "", theme: "",
  engine: "procedural", motif: "auto", ground: "white", placement: "center",
  texture: "print", variations: 3, seed: "",
  width: 1600, height: 900,
}

export function createCovers(settings: CoverSettings) {
  return apiRequest<{ task_id: string }>("/covers", {
    method: "POST", body: JSON.stringify(settings),
  })
}
