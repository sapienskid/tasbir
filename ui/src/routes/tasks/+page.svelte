<script lang="ts">
  import { onMount } from "svelte";
  import { listTasks } from "$lib/api/generate";

  let tasks = $state<{ id: string; status: string; progress?: number; created_at?: string }[]>([]);
  let loading = $state(true);
  let filter = $state("");

  onMount(async () => {
    try { tasks = await listTasks(50); } catch {} finally { loading = false; }
  });

  function timeAgo(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  function statusDot(s: string) {
    if (s === "completed") return "bg-white";
    if (s === "failed") return "bg-gray-600";
    if (s === "running") return "bg-gray-400";
    return "bg-gray-600";
  }

  const filtered = $derived(
    filter ? tasks.filter((t) => t.status === filter) : tasks
  );
</script>

<div class="p-8 max-w-3xl">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-lg font-medium text-white">Tasks</h1>
    <div class="flex gap-1.5">
      {#each ["", "pending", "running", "completed", "failed"] as f}
        <button
          class="text-xs px-2.5 py-1 rounded-full border transition-colors {filter === f ? 'bg-white text-black border-white' : 'bg-transparent text-gray-600 border-[#1c1c1c] hover:border-gray-600'}"
          onclick={() => (filter = f)}
        >
          {f || "all"}
        </button>
      {/each}
    </div>
  </div>

  {#if loading}
    <p class="text-sm text-gray-600">Loading…</p>
  {:else if filtered.length === 0}
    <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-8 text-center">
      <p class="text-sm text-gray-600">{filter ? `No ${filter} tasks` : "No tasks yet."}</p>
    </div>
  {:else}
    <div class="space-y-0.5">
      {#each filtered as task}
        <a
          href="/tasks/{task.id}"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors hover:bg-[#111]"
        >
          <span class="w-1.5 h-1.5 rounded-full shrink-0 {statusDot(task.status)}" />
          <span class="font-mono text-xs text-gray-600 w-20 shrink-0">{task.id.slice(0, 10)}</span>
          <span class="text-xs text-gray-500 flex-1 min-w-0 truncate">{task.status}</span>
          {#if task.progress !== undefined}
            <span class="text-xs text-gray-500 w-10 text-right">{task.progress}%</span>
          {/if}
          {#if task.created_at}
            <span class="text-xs text-gray-600 w-16 text-right shrink-0">{timeAgo(task.created_at)}</span>
          {/if}
        </a>
      {/each}
    </div>
  {/if}
</div>
