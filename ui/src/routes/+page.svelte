<script lang="ts">
  import { onMount } from "svelte";
  import Confirm from "$lib/components/ui/confirm.svelte";
  import { listTasks } from "$lib/api/generate";
  import { listTemplates } from "$lib/api/templates";
  import { listTokens } from "$lib/api/tokens";
  import { listFormats } from "$lib/api/formats";

  let templatesCount = $state(0);
  let tokensCount = $state(0);
  let formatsCount = $state(0);
  let assetsCount = $state(0);
  let recentTasks = $state<{ id: string; status: string; progress?: number; created_at?: string }[]>([]);
  let loading = $state(true);
  let acting = $state<string | null>(null);
  let confirm = $state<{ action: "cancel" | "retry"; id: string; title: string } | null>(null);

  const AGENTS = [
    { name: "Strategist", color: "#CD5B7D" },
    { name: "Copywriter", color: "#5B7D7C" },
    { name: "Visual Director", color: "#9B9BA0" },
    { name: "Designer", color: "#CD5B7D" },
    { name: "Quality Check", color: "#5B7D7C" },
    { name: "Renderer", color: "#9B9BA0" },
  ];

  onMount(async () => {
    try {
      const [tmpl, tok, fmt, tasks] = await Promise.all([
        listTemplates(false).catch(() => []),
        listTokens().catch(() => []),
        listFormats(false).catch(() => []),
        listTasks(10).catch(() => []),
      ]);
      templatesCount = tmpl.length;
      tokensCount = tok.length;
      formatsCount = fmt.length;
      assetsCount = tasks.filter((t: any) => t.status === "completed").length;
      recentTasks = (tasks as any[]).slice(0, 8);
    } catch {} finally { loading = false; }
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
    if (s === "completed") return "bg-[#22C55E]";
    if (s === "running") return "bg-[#3B82F6]";
    if (s === "failed") return "bg-[#EF4444]";
    if (s === "cancelled") return "bg-[#F59E0B]";
    return "bg-text-secondary/30";
  }

  function taskLabel(task: any) {
    if (task.status === "completed") return "Assets generated";
    if (task.status === "running") return "Generating assets…";
    if (task.status === "failed") return "Generation failed";
    if (task.status === "cancelled") return "Cancelled";
    return "Queued";
  }

  const API_BASE = "http://localhost:8000";

  async function cancelTask(id: string) {
    acting = id;
    try {
      await fetch(`${API_BASE}/tasks/${id}/cancel`, { method: "POST" });
      recentTasks = recentTasks.map(t => t.id === id ? { ...t, status: "cancelled", progress: 100 } : t);
    } catch { /* ignore */ }
    finally { acting = null; }
  }

  async function retryTask(id: string) {
    acting = id;
    try {
      await fetch(`${API_BASE}/tasks/${id}/retry`, { method: "POST" });
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
</script>

{#if loading}
  <div class="space-y-6 max-w-6xl">
    <div class="animate-pulse space-y-6">
      <div class="h-20 bg-surface rounded-xl"></div>
      <div class="flex gap-3">
        {#each [1,2,3] as _}
          <div class="h-20 flex-1 bg-surface rounded-xl"></div>
        {/each}
      </div>
        <div class="h-48 bg-surface rounded-xl"></div>
    </div>
  </div>
{:else}
  <div class="max-w-6xl space-y-8">
    <div>
      <h1 class="text-lg font-medium text-text" style="font-family: var(--font-display)">Dashboard</h1>
      <p class="text-sm text-text-secondary mt-0.5">{templatesCount} templates &middot; {formatsCount} formats &middot; {assetsCount} generations</p>
    </div>

    <!-- Pipeline hero -->
    <div class="rounded-xl border border-border bg-surface p-6">
      <div class="flex items-center justify-between mb-5">
        <h2 class="text-sm font-medium text-text">Pipeline</h2>
        <a href="/configure?tab=prompts" class="text-xs text-text-secondary hover:text-text transition-colors">Configure</a>
      </div>
      <div class="flex items-center gap-0 overflow-x-auto pb-2">
        {#each AGENTS as agent, i}
          <div class="flex items-center shrink-0">
            <div class="flex flex-col items-center gap-2">
              <div class="w-2 h-2 rounded-full" style="background:{agent.color}"></div>
              <span class="text-xs text-text-secondary whitespace-nowrap">{agent.name}</span>
            </div>
            {#if i < AGENTS.length - 1}
              <div class="w-10 sm:w-16 h-px bg-border mx-3"></div>
            {/if}
          </div>
        {/each}
      </div>
    </div>

    <!-- Stat cards -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <a href="/templates" class="rounded-xl border border-border bg-surface p-5 hover:border-border-focus transition-colors group">
        <p class="text-xs text-text-secondary mb-1">Templates</p>
        <p class="text-3xl text-text group-hover:text-accent transition-colors" style="font-family: var(--font-display)">{templatesCount}</p>
      </a>
      <a href="/tasks" class="rounded-xl border border-border bg-surface p-5 hover:border-border-focus transition-colors group">
        <p class="text-xs text-text-secondary mb-1">Generations</p>
        <p class="text-3xl text-text group-hover:text-accent transition-colors" style="font-family: var(--font-display)">{assetsCount}</p>
      </a>
      <a href="/configure?tab=formats" class="rounded-xl border border-border bg-surface p-5 hover:border-border-focus transition-colors group">
        <p class="text-xs text-text-secondary mb-1">Formats</p>
        <p class="text-3xl text-text group-hover:text-accent transition-colors" style="font-family: var(--font-display)">{formatsCount}</p>
      </a>
    </div>

    <!-- Quick create CTA -->
    <a href="/create" class="block rounded-xl border border-border bg-surface p-5 hover:border-accent/50 transition-colors group">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm text-text group-hover:text-accent transition-colors">New generation</p>
          <p class="text-xs text-text-secondary mt-1">Convert content into social media assets</p>
        </div>
        <span class="text-text-secondary group-hover:text-accent transition-colors">&rarr;</span>
      </div>
    </a>

    <!-- Recent tasks -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-medium text-text">Recent activity</h2>
      </div>

      {#if recentTasks.length === 0}
        <div class="rounded-xl border border-border bg-surface p-8 text-center">
          <p class="text-sm text-text-secondary">No activity yet.</p>
        </div>
      {:else}
        <div class="rounded-xl border border-border bg-surface divide-y divide-border">
          {#each recentTasks as task}
            <div class="flex items-center gap-4 px-5 py-3 hover:bg-elevated transition-colors">
              <a href="/tasks/{task.id}" class="flex items-center gap-4 flex-1 min-w-0">
                <span class="w-2 h-2 rounded-full shrink-0 {statusDot(task.status)}"></span>
                <span class="font-mono text-xs text-text-secondary w-16 shrink-0">{task.id.slice(0, 8)}</span>
                <span class="text-xs text-text flex-1 min-w-0 truncate">{taskLabel(task)}</span>
                <span class="text-xs text-text-secondary w-16 shrink-0">{task.status}</span>
                {#if task.progress !== undefined && task.status === "running"}
                  <div class="w-16 h-1 bg-border rounded-full overflow-hidden shrink-0">
                    <div class="h-full bg-accent rounded-full transition-all" style="width:{task.progress}%"></div>
                  </div>
                {/if}
                {#if task.created_at}
                  <span class="text-xs text-text-secondary w-14 text-right shrink-0">{timeAgo(task.created_at)}</span>
                {/if}
              </a>
              <div class="flex gap-1 shrink-0">
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
  </div>
{/if}

<Confirm
  open={confirm !== null}
  title={confirm?.action === "cancel" ? "Cancel task" : "Retry task"}
  message={confirm?.action === "cancel" ? `Cancel generation ${confirm?.title}?` : `Retry generation for task ${confirm?.title}?`}
  confirmLabel={confirm?.action === "cancel" ? "Cancel" : "Retry"}
  variant={confirm?.action === "cancel" ? "destructive" : "default"}
  onconfirm={handleConfirm}
  oncancel={() => confirm = null}
/>
