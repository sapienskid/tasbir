import useSWR from "swr"
import type { OutputFile, TaskDetail, TaskSummary } from "@/lib/api"

export function useTasks(status?: string) {
  return useSWR<TaskSummary[]>(`/tasks${status ? `?status=${encodeURIComponent(status)}` : ""}`)
}

export function useTask(taskId: string) {
  const taskSwr = useSWR<TaskDetail>(`/tasks/${taskId}`, {
    // Poll only while the pipeline is still working.
    refreshInterval: (latest) =>
      latest && (latest.status === "pending" || latest.status === "running") ? 2500 : 0,
  })

  const settled =
    taskSwr.data && (taskSwr.data.status === "completed" || taskSwr.data.status === "failed")

  const filesSwr = useSWR<OutputFile[] | null>(settled ? `/tasks/${taskId}/files` : null)

  return {
    task: taskSwr.data,
    error: taskSwr.error ?? filesSwr.error,
    isLoading: taskSwr.isLoading,
    mutate: taskSwr.mutate,
    files: filesSwr.data ?? [],
    filesError: filesSwr.error,
  }
}
