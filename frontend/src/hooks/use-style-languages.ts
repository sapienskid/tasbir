import useSWR from "swr"
import { listStyleLanguages, type StyleLanguage } from "@/lib/api"

/** The design languages a post can be rendered with (built-ins + customs). */
export function useStyleLanguages(): { styles: StyleLanguage[]; isLoading: boolean } {
  const { data, isLoading } = useSWR<StyleLanguage[]>("/design-systems/styles", listStyleLanguages, {
    refreshInterval: 0,
    revalidateOnFocus: false,
  })
  return { styles: data ?? [], isLoading }
}
