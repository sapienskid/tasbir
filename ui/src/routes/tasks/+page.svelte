<script lang="ts">
  import { onMount } from "svelte";
  import Confirm from "$lib/components/ui/confirm.svelte";
  import { listTasks } from "$lib/api/generate";

  const API_BASE = "http://localhost:8000";

  let tasks = $state<{ id: string; title: string; status: string; progress?: number; created_at?: string }[]>([]);
  let loading = $state(true);
  let filter = $state("");
  let acting = $state<string | null>(null);
  let confirm = $state<{ action: "cancel" | "retry"; id: string; title: string } | null>(null);

  const FILTERS = ["", "pending", "running", "completed", "failed", "cancelled"];

  onMount(async () => {
    try {
      tasks = await listTasks(50) as any;
    } catch { /* empty */ }
    finally { loading = false; }
  });

  function statusDot(s: string) {
    if (s === "completed") return "bg-[#22C55E]";
    if (s === "running") return "bg-[#3B82F6]";
    if (s === "failed") return "bg-[#EF4444]";
    if (s === "cancelled") return "bg-[#F59E0B]";
    return "bg-text-secondary/30";
  }

  function timeAgo(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  async function cancelTask(id: string) {
    acting = id;
    try {
      await fetch(`${API_BASE}/tasks/${id}/cancel`, { method: "POST" });
      tasks = tasks.map(t => t.id === id ? { ...t, status: "cancelled", progress: 100 } : t);
    } catch { /* ignore */ }
    finally { acting = null; }
  }

  async function retryTask(id: string) {
    acting = id;
    try {
      const res = await fetch(`${API_BASE}/tasks/${id}/retry`, { method: "POST" });
      const data = await res.json();
      if (data.task_id) {
        tasks = [{ id: data.task_id, title: "Retry", status: "pending", progress: 0, created_at: new Date().toISOString() }, ...tasks];
      }
    } catch { /* ignore */ }
    finally { acting = null; }
  }

  function handleConfirm() {
    if (!confirm) return;
    const c = confirm;
    confirm = null;
    if (c.action === "cancel") cancelTask(c.id);
    else retryTask(c.id);
  }

  const filtered = $derived(
    filter ? tasks.filter((t) => t.status === filter) : tasks
  );
</script>

<div class="max-w-5xl space-y-6">
  <div>
    <h1 class="text-lg font-medium text-text" style="font-family: var(--font-display)">Tasks</h1>
    <p class="text-sm text-text-secondary mt-0.5">{tasks.length} total tasks</p>
  </div>

  <div class="flex gap-1.5 flex-wrap">
    {#each FILTERS as f}
      <button
        class="text-xs px-3 py-1 rounded-full border transition-colors {!f && !filter || filter === f ? 'bg-accent text-white border-accent' : 'bg-transparent text-text-secondary border-border hover:border-border-focus'}"
        onclick={() => filter = f}
      >
        {f || "All"}
      </button>
    {/each}
  </div>

  {#if loading}
    <p class="text-sm text-text-secondary">Loading…</p>
  {:else if filtered.length === 0}
    <div class="rounded-xl border border-border bg-surface p-8 text-center">
      <p class="text-sm text-text-secondary">No tasks found.</p>
    </div>
  {:else}
    <div class="rounded-xl border border-border bg-surface divide-y divide-border">
      {#each filtered as task}
        <div class="flex items-center gap-4 px-5 py-3 hover:bg-elevated transition-colors">
          <a href="/tasks/{task.id}" class="flex items-center gap-4 flex-1 min-w-0">
            <span class="w-2 h-2 rounded-full shrink-0 {statusDot(task.status)}"></span>
            <span class="font-mono text-xs text-text-secondary w-16 shrink-0">{task.id.slice(0, 8)}</span>
            <span class="text-xs text-text flex-1 min-w-0 truncate">{task.title || task.id.slice(0, 10)}</span>
            <span class="text-xs text-text-secondary w-16 shrink-0">{task.status}</span>
            {#if task.progress !== undefined}
              <span class="text-xs text-text-secondary w-10 text-right">{task.progress}%</span>
            {/if}
            {#if task.created_at}
              <span class="text-xs text-text-secondary w-14 text-right shrink-0">{timeAgo(task.created_at)}</span>
            {/if}
          </a>
          <div class="flex gap-1.5 shrink-0">
            {#if task.status === "running" || task.status === "pending"}
              <button onclick={() => confirm = { action: "cancel", id: task.id, title: task.id.slice(0, 8) }} disabled={acting === task.id} class="text-[11px] text-text-secondary hover:text-destructive transition-colors">
                {acting === task.id ? "..." : "Cancel"}
              </button>
            {/if}
            {#if task.status === "failed" || task.status === "cancelled"}
              <button onclick={() => confirm = { action: "retry", id: task.id, title: task.id.slice(0, 8) }} disabled={acting === task.id} class="text-[11px] text-text-secondary hover:text-accent transition-colors">
                {acting === task.id ? "..." : "Retry"}
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<Confirm
  open={confirm !== null}
  title={confirm?.action === "cancel" ? "Cancel task" : "Retry task"}
  message={confirm?.action === "cancel" ? `Cancel generation ${confirm?.title}?` : `Retry generation for task ${confirm?.title}?`}
  confirmLabel={confirm?.action === "cancel" ? "Cancel" : "Retry"}
  variant={confirm?.action === "cancel" ? "destructive" : "default"}
  onconfirm={handleConfirm}
  oncancel={() => confirm = null}
/>
