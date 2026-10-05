import useSWR from "swr"
import type { PlatformInfo } from "@/lib/api"
import { listPlatforms } from "@/lib/api"
import { loadPlatforms } from "@/lib/platforms"

/** Load the DB platforms.
 *
 *  The active-only path also populates the module dimension caches (via
 *  `loadPlatforms`). `includeInactive` adds deactivated rows for the Settings
 *  table without touching those caches, so a hidden platform can never change a
 *  render size. */
export function usePlatforms(includeInactive = false): {
  platforms: PlatformInfo[]
  isLoading: boolean
  mutate: () => Promise<unknown>
} {
  const key = includeInactive ? "/platforms?include_inactive=true" : "/platforms"
  const fetcher = includeInactive ? () => listPlatforms(true) : loadPlatforms
  const { data, isLoading, mutate } = useSWR<PlatformInfo[]>(key, fetcher, {
    refreshInterval: 0,
  })
  return { platforms: data ?? [], isLoading, mutate }
}
