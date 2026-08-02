/** Shared format helpers for the task-detail gallery + editor. */

export function formatLabel(fmt: string): string {
  const m = /^instagram-carousel-(\d+)$/.exec(fmt)
  if (m) return `Slide ${m[1]}`
  if (fmt === "instagram-carousel") return "Carousel"
  return fmt
}

/** Step status dot: green = verified, amber = running/queued, red = failed. */
export function StepDot({ status }: { status: string }) {
  const color =
    status === "verified"
      ? "bg-emerald-500"
      : status === "failed" || status === "error"
        ? "bg-destructive"
        : "bg-amber-400 animate-pulse"
  return <span className={`inline-block size-2 rounded-full ${color}`} />
}

export function groupFormats(formats: string[]): { group: string; items: string[] }[] {
  const squareSlides = formats.filter((f) => /^instagram-carousel-\d+$/.test(f))
  const portraitSlides = formats.filter((f) => /^instagram-carousel-portrait-\d+$/.test(f))
  const singles = formats.filter((f) => !squareSlides.includes(f) && !portraitSlides.includes(f))
  const groups: { group: string; items: string[] }[] = []
  if (singles.length) groups.push({ group: "Posts", items: singles })
  if (squareSlides.length) groups.push({ group: "Carousel · square", items: squareSlides })
  if (portraitSlides.length) groups.push({ group: "Carousel · portrait", items: portraitSlides })
  return groups
}
