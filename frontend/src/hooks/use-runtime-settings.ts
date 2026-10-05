import useSWR, { type KeyedMutator } from "swr"
import type { RuntimeSettingsResponse } from "@/lib/api"
import { getRuntimeSettings } from "@/lib/api"

/** Runtime tuning knobs (defaults carry the server-side type contract).
 *
 *  `mutate` is the full SWR mutator so a write can adopt the server's response
 *  (`mutate(res, { revalidate: false })`) instead of refetching. */
export function useRuntimeSettings(): {
  data: RuntimeSettingsResponse | undefined
  isLoading: boolean
  mutate: KeyedMutator<RuntimeSettingsResponse>
} {
  const { data, isLoading, mutate } = useSWR<RuntimeSettingsResponse>(
    "/settings",
    getRuntimeSettings,
    { refreshInterval: 0 },
  )
  return { data, isLoading, mutate }
}
