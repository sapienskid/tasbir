import useSWR from "swr"
import {
  getAgentGraph,
  listAgents,
  getAgentJob,
  listDesignSystems,
  listTemplates,
  previewTemplate,
  type AgentConfig,
  type AgentGraphSpec,
  type AgentJob,
  type DesignSystem,
  type Template,
} from "@/lib/api"

export function useDesignSystems(): {
  data: DesignSystem[] | undefined
  error: unknown
  isLoading: boolean
  mutate: () => Promise<unknown>
} {
  return useSWR("/design-systems", () => listDesignSystems())
}

export function useTemplates(
  designSystemId: string | null,
  family?: string,
  includeInactive = false
): {
  data: Template[] | undefined
  error: unknown
  isLoading: boolean
  mutate: () => Promise<unknown>
} {
  const key = designSystemId
    ? `/templates?ds=${designSystemId}&fam=${family ?? ""}&inc=${includeInactive ? 1 : 0}`
    : null
  return useSWR(key, () =>
    listTemplates(designSystemId ?? "default", family, includeInactive)
  )
}

export function useAgentJob(jobId: string | null): {
  data: AgentJob | undefined
  error: unknown
} {
  return useSWR(
    jobId ? `/agent-jobs/${jobId}` : null,
    () => getAgentJob(jobId as string),
    {
      refreshInterval: (job: AgentJob | undefined) =>
        job && (job.status === "pending" || job.status === "running") ? 3000 : 0,
    }
  )
}

export function isJobDone(job: AgentJob | undefined): boolean {
  return Boolean(job && (job.status === "completed" || job.status === "failed"))
}

export function useAgents(): {
  data: AgentConfig[] | undefined
  error: unknown
  isLoading: boolean
  mutate: () => Promise<unknown>
} {
  return useSWR("/agents", () => listAgents())
}

export function useAgentGraph(): {
  data: AgentGraphSpec | undefined
  error: unknown
  isLoading: boolean
  mutate: () => Promise<unknown>
} {
  return useSWR("/agents/graph", () => getAgentGraph())
}

/**
 * Cached template preview HTML keyed by template id. SWR dedupes concurrent
 * requests and keeps the preview warm when the card re-mounts, so galleries
 * with many templates don't re-fire a render per card on every visit.
 */
export function useTemplatePreview(id: string): {
  data: { html: string } | null
  failed: boolean
  retry: () => void
} {
  const { data, error, mutate } = useSWR(
    id ? `/templates/${id}/preview` : null,
    () => previewTemplate(id),
    {
      // Preview renders are POSTs (server-side render) — keep them cached for
      // the session instead of re-running on every gallery mount.
      dedupingInterval: Infinity,
      keepPreviousData: true,
    }
  )
  return {
    data: error ? null : (data ?? null),
    failed: Boolean(error),
    retry: () => void mutate(),
  }
}
