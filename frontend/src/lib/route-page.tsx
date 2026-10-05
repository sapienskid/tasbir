import { Suspense, type ReactNode } from "react"

function FullPageSkeleton() {
  return (
    <div className="grid gap-4">
      <div className="h-8 w-1/3 animate-pulse rounded-md bg-muted" />
      <div className="h-96 animate-pulse rounded-md border bg-muted/30" />
    </div>
  )
}

/** Wrap a lazily-loaded route element in Suspense with the shared skeleton.
 *
 *  Lives in its own module so App.tsx and the settings route tree can both
 *  build routes without importing each other. */
export function page(node: ReactNode) {
  return <Suspense fallback={<FullPageSkeleton />}>{node}</Suspense>
}
