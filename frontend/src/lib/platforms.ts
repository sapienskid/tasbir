// DB-backed platform config. The Studio owns the rows; this module keeps a
// warm module cache so sync helpers (formatDims / FAMILY_DIMS) work everywhere
// without threading async state through every consumer. `loadPlatforms()`
// refreshes it; `usePlatforms()` also triggers a re-render on change.

import type { PlatformInfo } from "./api"
import { listPlatforms } from "./api"

export type { PlatformInfo }

export interface Dimensions {
  width: number
  height: number
}

const SQUARE: Dimensions = { width: 1080, height: 1080 }

// Fallback defaults — correct for the seed system; overwritten on load.
export const FAMILY_DIMS: Record<string, Dimensions> = {
  square: SQUARE,
  portrait: { width: 1080, height: 1350 },
  story: { width: 1080, height: 1920 },
  landscape: { width: 1200, height: 627 },
}

export const FORMAT_DIMS: Record<string, Dimensions> = {
  "instagram-square": SQUARE,
  "instagram-carousel": SQUARE,
  "instagram-carousel-portrait": { width: 1080, height: 1350 },
  "instagram-portrait": { width: 1080, height: 1350 },
  "instagram-story": { width: 1080, height: 1920 },
  "linkedin-post": { width: 1200, height: 627 },
  "twitter-card": { width: 1200, height: 675 },
  "facebook-post": { width: 1200, height: 630 },
  "pinterest-pin": { width: 1000, height: 1500 },
}

const _SLIDE_RE = /^(instagram-carousel(?:-portrait)?)-(\d+)$/

/** Fetch platforms and populate the module caches. */
export async function loadPlatforms(): Promise<PlatformInfo[]> {
  const rows = await listPlatforms()
  const byId: Record<string, PlatformInfo> = {}
  // Build a family → first-active-platform map once (instead of a find per
  // family in the loop below).
  const firstByFamily: Record<string, PlatformInfo> = {}
  for (const row of rows) {
    byId[row.id] = row
    FORMAT_DIMS[row.id] = { width: row.width, height: row.height }
    if (!(row.family in firstByFamily)) firstByFamily[row.family] = row
  }
  for (const fam of Object.keys(FAMILY_DIMS)) {
    const first = firstByFamily[fam]
    if (first) FAMILY_DIMS[fam] = { width: first.width, height: first.height }
  }
  return rows
}

/** Current platform ids (includes the default seed set before load). */
export function knownPlatforms(): string[] {
  return Object.keys(FORMAT_DIMS)
}

export function platformDims(format: string): Dimensions | null {
  const exact = FORMAT_DIMS[format]
  if (exact) return exact
  const m = _SLIDE_RE.exec(format)
  if (m && FORMAT_DIMS[m[1]]) return FORMAT_DIMS[m[1]]
  return null
}

export function formatDims(format: string): Dimensions {
  return platformDims(format) ?? SQUARE
}

export function familyOfPlatform(format: string): string {
  const m = _SLIDE_RE.exec(format)
  const base = m ? m[1] : format
  const d = platformDims(base)
  if (!d) return "square"
  return d.height > d.width ? "portrait" : d.width > d.height ? "landscape" : "square"
}
