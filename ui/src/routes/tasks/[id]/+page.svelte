<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { page } from "$app/stores";
  import { Card } from "$lib/components/ui/card/index.js";
  import LangGraphVisualizer from "$lib/components/LangGraphVisualizer.svelte";
  import { getTask, type TaskResult } from "$lib/api/generate";
  import { getSocket, connectSocket, joinTaskRoom } from "$lib/stores/socket";
  import { activeTask } from "$lib/stores/activeTask";
  import { API_BASE } from "$lib/api/config";

  let task = $state<TaskResult | null>(null);
  let assets = $state<Record<string, string>>({});
  let loading = $state(true);
  let error = $state("");

  let cleanup: (() => void) | null = null;

  function assetUrl(url: string): string {
    if (url.startsWith("/")) return `${API_BASE}${url}`;
    return url;
  }

  function statusColor(s: string) {
    if (s === "completed") return "text-[#22C55E]";
    if (s === "running") return "text-[#3B82F6]";
    if (s === "failed") return "text-[#EF4444]";
    if (s === "cancelled") return "text-[#F59E0B]";
    return "text-text-secondary";
  }

  onMount(async () => {
    const taskId = $page.params.id;
    try {
      task = await getTask(taskId);
      loading = false;

      if (task.status === "running" || task.status === "pending") {
        // Update the shared activeTask store so dashboard/create see progress
        activeTask.setTaskId(taskId, (task.source_data?.title as string) || "");
        (async () => {
          await connectSocket();
          await joinTaskRoom(taskId);
          const socket = await getSocket();
          if (!socket) return;

          const onProgress = (data: any) => {
            if (task) { task.status = data.status; task.progress = data.percent; }
          };

          const onComplete = (data: any) => {
            if (task) {
              task.status = "completed";
              task.progress = 100;
              task.result = data.result;
              const raw = data.result?.assets_by_format as Record<string, string> || {};
              const resolved: Record<string, string> = {};
              for (const [k, v] of Object.entries(raw)) resolved[k] = assetUrl(v);
              assets = resolved;
            }
          };

          socket.on("progress", onProgress);
          socket.on("complete", onComplete);
          cleanup = () => { socket.off("progress", onProgress); socket.off("complete", onComplete); };
        })();
      } else if (task.status === "completed" && task.result?.assets_by_format) {
        const raw = task.result.assets_by_format as Record<string, string>;
        for (const [k, v] of Object.entries(raw)) raw[k] = assetUrl(v);
        assets = raw;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load task";
      loading = false;
    }
  });

  onDestroy(() => cleanup?.());
</script>

<div class="max-w-4xl space-y-6">
  <a href="/assets" class="inline-flex items-center text-xs text-text-secondary hover:text-text transition-colors">&larr; Assets</a>

  {#if loading}
    <p class="text-sm text-text-secondary">Loading…</p>
  {:else if error}
    <Card class="p-5">
      <p class="text-sm text-text-secondary">{error}</p>
    </Card>
  {:else if task}
    <Card class="p-5">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <span class="text-xs font-mono text-text-secondary">{task.id.slice(0, 12)}</span>
          <span class="text-xs text-text-secondary">{new Date(task.created_at).toLocaleString()}</span>
        </div>
        <span class="text-xs {statusColor(task.status)}">{task.status}</span>
      </div>

      {#if task.status === "running"}
        <div class="w-full h-1.5 bg-border rounded-full overflow-hidden mb-4">
          <div class="h-full bg-[#3B82F6] rounded-full transition-all duration-500" style="width: {task.progress}%"></div>
        </div>
        <LangGraphVisualizer
          activeNode={$activeTask.activeNode}
          progress={$activeTask.progress}
          qualityScore={$activeTask.qualityScore}
        />
      {/if}

      {#if task.status === "failed" && task.error}
        <p class="text-xs text-destructive mt-3">{task.error}</p>
      {/if}
    </Card>

    {#if task.status === "completed" && Object.keys(assets).length > 0}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {#each Object.entries(assets) as [fmt, url]}
          <Card class="overflow-hidden">
            <div class="px-4 py-2.5 border-b border-border flex items-center justify-between">
              <span class="text-xs font-mono text-text-secondary">{fmt}</span>
              <a href={assetUrl(url)} target="_blank" class="text-xs text-text-secondary hover:text-accent transition-colors">open</a>
            </div>
            <div class="bg-bg flex items-center justify-center min-h-[240px]">
              <img src={assetUrl(url)} alt={fmt} class="max-w-full h-auto" loading="lazy" />
            </div>
          </Card>
        {/each}
      </div>
    {/if}
  {/if}
</div>
