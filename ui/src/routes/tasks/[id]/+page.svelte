<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { page } from "$app/stores";
  import Button from "$lib/components/ui/button.svelte";
  import { getTask, streamTask, type TaskResult } from "$lib/api/generate";

  let task = $state<TaskResult | null>(null);
  let assets = $state<Record<string, string>>({});
  let loading = $state(true);
  let error = $state("");

  let cleanup: (() => void) | null = null;

  onMount(async () => {
    const taskId = $page.params.id;
    try {
      task = await getTask(taskId);
      loading = false;

      if (task.status === "running" || task.status === "pending") {
        cleanup = streamTask(
          taskId,
          (data) => {
            if (task) { task.status = data.status; task.progress = data.progress; }
          },
          (data) => {
            if (task) {
              task.status = "completed";
              task.result = data.result;
              task.progress = 100;
              if (data.result?.assets_by_format) assets = data.result.assets_by_format as Record<string, string>;
            }
          },
          (err) => { error = err; }
        );
      } else if (task.status === "completed" && task.result?.assets_by_format) {
        assets = task.result.assets_by_format as Record<string, string>;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load task";
      loading = false;
    }
  });

  onDestroy(() => cleanup?.());
</script>

<div class="p-8 max-w-2xl">
  <a href="/" class="inline-block text-xs text-gray-600 hover:text-white transition-colors mb-5">&larr; Dashboard</a>

  {#if loading}
    <p class="text-sm text-gray-600">Loading…</p>
  {:else if error}
    <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-5">
      <p class="text-sm text-gray-600">{error}</p>
    </div>
  {:else if task}
    <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-5 mb-6">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <span class="text-xs font-mono text-gray-600">{task.id.slice(0, 12)}</span>
          <span class="text-xs text-gray-600">{new Date(task.created_at).toLocaleString()}</span>
        </div>
        <span class="text-xs {task.status === 'completed' ? 'text-white' : task.status === 'failed' ? 'text-gray-600' : 'text-gray-500'}">{task.status}</span>
      </div>

      {#if task.status === "running"}
        <div class="w-full h-1 bg-[#1c1c1c] rounded-full overflow-hidden">
          <div class="h-full bg-white rounded-full transition-all duration-500" style="width: {task.progress}%"></div>
        </div>
      {/if}

      {#if task.status === "failed" && task.error}
        <p class="text-xs text-gray-600 mt-3">{task.error}</p>
      {/if}
    </div>

    {#if task.status === "completed" && Object.keys(assets).length > 0}
      <p class="text-xs text-gray-600 mb-3">Assets</p>
      <div class="space-y-3">
        {#each Object.entries(assets) as [fmt, url]}
          <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] overflow-hidden">
            <div class="px-4 py-2 border-b border-[#1c1c1c] flex items-center justify-between">
              <span class="text-xs font-mono text-gray-500">{fmt}</span>
              <a href={url} target="_blank" class="text-xs text-gray-600 hover:text-white transition-colors">open</a>
            </div>
            <div class="bg-black flex items-center justify-center min-h-[200px]">
              <img src={url} alt={fmt} class="max-w-full h-auto" loading="lazy" />
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
