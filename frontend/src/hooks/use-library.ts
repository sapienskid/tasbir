import useSWR from "swr"
import {
  getAgentJob,
  listDesignSystems,
  listTemplates,
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
