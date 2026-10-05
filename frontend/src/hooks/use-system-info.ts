import useSWR from "swr"
import type { SystemInfo } from "@/lib/api"
import { getSystemInfo } from "@/lib/api"

/** Read-only view of the environment in force (no secrets — booleans only). */
export function useSystemInfo(): {
  info: SystemInfo | undefined
  isLoading: boolean
  error: unknown
} {
  const { data, isLoading, error } = useSWR<SystemInfo>("/system/info", getSystemInfo, {
    refreshInterval: 0,
    revalidateOnFocus: false,
  })
  return { info: data, isLoading, error }
}
