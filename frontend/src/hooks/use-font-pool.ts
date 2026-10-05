import useSWR from "swr"
import type { PoolFont } from "@/lib/api"
import { listFontPool } from "@/lib/api"

/** The curated Google Fonts pool (DB-backed, Studio-owned). */
export function useFontPool(includeInactive = false): {
  fonts: PoolFont[]
  isLoading: boolean
  mutate: () => Promise<unknown>
} {
  const key = includeInactive ? "/fonts/pool?include_inactive=true" : "/fonts/pool"
  const { data, isLoading, mutate } = useSWR<PoolFont[]>(key, () => listFontPool(includeInactive), {
    refreshInterval: 0,
  })
  return { fonts: data ?? [], isLoading, mutate }
}
