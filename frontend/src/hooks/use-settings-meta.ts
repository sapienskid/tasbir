import useSWR from "swr"
import type { SettingsMeta } from "@/lib/api"
import { getSettingsMeta } from "@/lib/api"

// Last-resort values, used only while the request is in flight or if it failed —
// the backend owns these lists (GET /api/settings/meta) so the Studio never
// hardcodes them.
const FALLBACK: SettingsMeta = {
  families: ["landscape", "portrait", "square", "story"],
  font_roles: ["display", "mono", "sans", "serif"],
}

/** Platform families + font roles, from the backend's single source of truth. */
export function useSettingsMeta(): {
  meta: SettingsMeta
  isLoading: boolean
} {
  const { data, isLoading } = useSWR<SettingsMeta>("/settings/meta", getSettingsMeta, {
    refreshInterval: 0,
    revalidateOnFocus: false,
  })
  return { meta: data ?? FALLBACK, isLoading }
}
