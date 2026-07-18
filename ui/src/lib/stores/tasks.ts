import { writable, derived } from "svelte/store";
import { listTasks, type TaskResult } from "$lib/api/generate";

interface TaskState {
  items: TaskSummary[];
  loading: boolean;
  error: string | null;
}

interface TaskSummary {
  id: string;
  status: string;
  progress: number;
  created_at: string;
}

function createTaskStore() {
  const { subscribe, update, set } = writable<TaskState>({
    items: [],
    loading: false,
    error: null,
  });

  return {
    subscribe,
    async fetch(limit = 20) {
      update((s) => ({ ...s, loading: true, error: null }));
      try {
        const items = await listTasks(limit);
        update((s) => ({ ...s, items, loading: false }));
      } catch (e) {
        update((s) => ({
          ...s,
          loading: false,
          error: e instanceof Error ? e.message : "Failed to load tasks",
        }));
      }
    },
    addTask(taskId: string) {
      update((s) => ({
        ...s,
        items: [
          {
            id: taskId,
            status: "pending",
            progress: 0,
            created_at: new Date().toISOString(),
          },
          ...s.items,
        ],
      }));
    },
  };
}

export const taskStore = createTaskStore();
