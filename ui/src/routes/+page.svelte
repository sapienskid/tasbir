<script lang="ts">
  import { onMount } from "svelte";
  import Confirm from "$lib/components/ui/confirm.svelte";
  import { listTasks } from "$lib/api/generate";
  import { listTemplates } from "$lib/api/templates";
  import { listTokens } from "$lib/api/tokens";
  import { listFormats } from "$lib/api/formats";
  import { activeTask } from "$lib/stores/activeTask";
  import LangGraphVisualizer from "$lib/components/LangGraphVisualizer.svelte";
  import { API_BASE } from "$lib/api/config";

  let templatesCount = $state(0);
  let tokensCount = $state(0);
  let formatsCount = $state(0);
  let assetsCount = $state(0);
  let recentTasks = $state<{ id: string; status: string; progress?: number; created_at?: string }[]>([]);
  let loading = $state(true);
  let acting = $state<string | null>(null);
  let confirm = $state<{ action: "cancel" | "retry"; id: string; title: string } | null>(null);
  let actionError = $state("");

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

  async function cancelTask(id: string) {
    acting = id;
    actionError = "";
    try {
      await api.post(`/tasks/${id}/cancel`);
      recentTasks = recentTasks.map(t => t.id === id ? { ...t, status: "cancelled", progress: 100 } : t);
    } catch (e) {
      actionError = e instanceof Error ? e.message : "Cancel failed";
    }
    finally { acting = null; }
  }

  async function retryTask(id: string) {
    acting = id;
    actionError = "";
    try {
      await api.post(`/tasks/${id}/retry`);
    } catch (e) {
      actionError = e instanceof Error ? e.message : "Retry failed";
    }
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

{#if actionError}
  <div class="max-w-6xl rounded-xl border border-destructive/30 bg-destructive/5 p-3 mb-4">
    <p class="text-xs text-destructive">{actionError}</p>
  </div>
{/if}

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

    <!-- Active Generation / LangGraph execution -->
    {#if $activeTask.taskId}
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full {$activeTask.status === 'completed' ? 'bg-accent' : 'bg-blue-500 animate-ping'}"></span>
            <h2 class="text-sm font-medium text-text">Active Generation: {$activeTask.title || $activeTask.taskId.slice(0, 8)}</h2>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs font-mono text-text-secondary">{$activeTask.progress}%</span>
            <button onclick={() => activeTask.clear()} class="text-xs text-text-secondary hover:text-text">Clear</button>
          </div>
        </div>

        <LangGraphVisualizer
          activeNode={$activeTask.activeNode}
          progress={$activeTask.progress}
          qualityScore={$activeTask.qualityScore}
        />

        {#if Object.keys($activeTask.assets).length > 0}
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {#each Object.entries($activeTask.assets) as [fmt, url]}
              <a href={url} target="_blank" class="block rounded-lg border border-border bg-bg overflow-hidden hover:border-accent transition-colors">
                <img src={url} alt={fmt} class="w-full aspect-square object-cover" />
                <div class="p-1.5 text-[10px] font-mono text-text-secondary truncate text-center">{fmt}</div>
              </a>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <LangGraphVisualizer />
    {/if}

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
