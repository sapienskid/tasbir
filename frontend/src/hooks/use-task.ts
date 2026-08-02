import useSWR from "swr"
import type {
  OutputFile,
  TaskDetail,
  TaskProgress,
  TaskSummary,
} from "@/lib/api"
import { getTaskProgress } from "@/lib/api"

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

/** Live pipeline progress for a task; polls while the task is running. */
export function useTaskProgress(taskId: string, active: boolean) {
  return useSWR<TaskProgress>(
    active ? `/tasks/${taskId}/progress` : null,
    () => getTaskProgress(taskId),
    { refreshInterval: active ? 2500 : 0 }
  )
}
