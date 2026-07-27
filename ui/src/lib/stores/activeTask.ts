import { browser } from "$app/environment";
import { writable, get } from "svelte/store";
import { getSocket, connectSocket, joinTaskRoom } from "$lib/stores/socket";

const API_BASE =
  (typeof import.meta !== "undefined" && import.meta.env?.PUBLIC_API_URL) ||
  "http://localhost:8000";

export interface ActiveTaskState {
  taskId: string;
  status: string;
  progress: number;
  activeNode: string;
  title: string;
  assets: Record<string, string>;
  qualityScore: number;
  error: string | null;
}

const STORAGE_KEY = "tasbir:active_task_id";

function determineNode(progress: number, status: string): string {
  if (status === "completed") return "END";
  if (status === "failed") return "failed";
  if (progress < 25) return "strategist";
  if (progress < 45) return "copywriter";
  if (progress < 65) return "visual_director";
  if (progress < 80) return "designer";
  if (progress < 92) return "quality_check";
  return "renderer";
}

const initialState: ActiveTaskState = {
  taskId: browser ? localStorage.getItem(STORAGE_KEY) || "" : "",
  status: "",
  progress: 0,
  activeNode: "",
  title: "",
  assets: {},
  qualityScore: 0,
  error: null,
};

const _store = writable<ActiveTaskState>(initialState);

function resolveAssetUrl(url: string): string {
  if (url.startsWith("/")) return `${API_BASE}${url}`;
  return url;
}

function extractAssets(result: any): Record<string, string> {
  const map: Record<string, string> = {};
  if (result?.assets_by_format) {
    for (const [k, v] of Object.entries(result.assets_by_format as Record<string, string>)) {
      map[k] = resolveAssetUrl(v);
    }
  }
  return map;
}

let cleanupHandlers: (() => void)[] = [];

async function subscribeToTask(taskId: string) {
  cleanupHandlers.forEach((fn) => fn());
  cleanupHandlers = [];

  await connectSocket();
  await joinTaskRoom(taskId);

  const socket = await getSocket();
  if (!socket) return;

  const onProgress = (data: any) => {
    _store.update((s) => ({
      ...s,
      status: data.status || s.status,
      progress: data.percent ?? s.progress,
      activeNode: determineNode(data.percent ?? s.progress, data.status || s.status),
      assets: Object.keys(extractAssets(data.result)).length > 0 ? extractAssets(data.result) : s.assets,
      error: data.status === "failed" ? data.error || "Generation failed" : s.error,
    }));
  };

  const onComplete = (data: any) => {
    _store.update((s) => ({
      ...s,
      status: "completed",
      progress: 100,
      activeNode: "END",
      assets: extractAssets(data.result),
      qualityScore: data.result?.quality_score ?? s.qualityScore,
      error: null,
    }));
    if (browser) localStorage.removeItem(STORAGE_KEY);
  };

  socket.on("progress", onProgress);
  socket.on("complete", onComplete);

  cleanupHandlers = [
    () => socket.off("progress", onProgress),
    () => socket.off("complete", onComplete),
  ];
}

if (browser && initialState.taskId) {
  subscribeToTask(initialState.taskId);
}

if (browser && "BroadcastChannel" in window) {
  const channel = new BroadcastChannel("tasbir:task");
  channel.onmessage = (event) => {
    if (event.data?.type === "task-started") {
      subscribeToTask(event.data.taskId);
    }
  };
  cleanupHandlers.push(() => channel.close());
}

export const activeTask = {
  subscribe: _store.subscribe,

  get current(): ActiveTaskState {
    return get(_store);
  },

  setTaskId(id: string, initialTitle = "") {
    _store.set({
      taskId: id,
      status: "running",
      progress: 5,
      activeNode: "strategist",
      title: initialTitle,
      assets: {},
      qualityScore: 0,
      error: null,
    });
    if (browser) {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    }
    subscribeToTask(id);

    if (browser && "BroadcastChannel" in window) {
      const channel = new BroadcastChannel("tasbir:task");
      channel.postMessage({ type: "task-started", taskId: id });
    }
  },

  clear() {
    cleanupHandlers.forEach((fn) => fn());
    cleanupHandlers = [];
    _store.set({
      taskId: "",
      status: "",
      progress: 0,
      activeNode: "",
      title: "",
      assets: {},
      qualityScore: 0,
      error: null,
    });
    if (browser) localStorage.removeItem(STORAGE_KEY);
  },
};
