import useSWR from "swr"
import type { PlatformInfo } from "@/lib/api"
import { loadPlatforms } from "@/lib/platforms"

/** Load the DB platforms and populate the module dimension caches. */
export function usePlatforms(): {
  platforms: PlatformInfo[]
  isLoading: boolean
  mutate: () => Promise<unknown>
} {
  const { data, isLoading, mutate } = useSWR<PlatformInfo[]>("/platforms", loadPlatforms, {
    refreshInterval: 0,
  })
  return { platforms: data ?? [], isLoading, mutate }
}
