<script lang="ts">
  import { onMount } from "svelte";
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

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

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
    if (s === "completed") return "bg-white";
    if (s === "failed") return "bg-gray-600";
    if (s === "running") return "bg-gray-400";
    return "bg-gray-600";
  }

  function statusClass(s: string) {
    if (s === "completed") return "text-white";
    if (s === "failed") return "text-gray-600";
    return "text-gray-500";
  }
</script>

{#if loading}
  <div class="p-8 max-w-4xl">
    <div class="animate-pulse space-y-6">
      <div class="h-7 w-56 bg-[#111] rounded" />
      <div class="flex gap-3">
        {#each [1,2,3,4] as _}
          <div class="h-16 flex-1 bg-[#111] rounded-lg" />
        {/each}
      </div>
      <div class="h-48 bg-[#111] rounded-lg" />
    </div>
  </div>
{:else}
  <div class="p-8 max-w-4xl">
    <div class="mb-7">
      <h1 class="text-lg font-medium text-white">{greeting}</h1>
      <p class="text-sm text-gray-600 mt-0.5">{templatesCount} templates &middot; {tokensCount} tokens &middot; {formatsCount} formats &middot; {assetsCount} assets generated</p>
    </div>

    <div class="grid grid-cols-4 gap-3 mb-7">
      <a href="/templates" class="block rounded-lg border border-[#1c1c1c] bg-[#080808] p-3.5 hover:border-[#333] transition-colors">
        <p class="text-xs text-gray-600 mb-0.5">Templates</p>
        <p class="text-xl font-medium text-white">{templatesCount}</p>
      </a>
      <a href="/tokens" class="block rounded-lg border border-[#1c1c1c] bg-[#080808] p-3.5 hover:border-[#333] transition-colors">
        <p class="text-xs text-gray-600 mb-0.5">Tokens</p>
        <p class="text-xl font-medium text-white">{tokensCount}</p>
      </a>
      <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-3.5">
        <p class="text-xs text-gray-600 mb-0.5">Formats</p>
        <p class="text-xl font-medium text-white">{formatsCount}</p>
      </div>
      <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-3.5">
        <p class="text-xs text-gray-600 mb-0.5">Assets</p>
        <p class="text-xl font-medium text-white">{assetsCount}</p>
      </div>
    </div>

    <div class="flex gap-4 mb-7">
      <a href="/generate" class="flex items-center justify-between flex-1 rounded-lg border border-[#1c1c1c] bg-[#080808] px-4 py-3.5 hover:border-[#333] transition-colors group">
        <div>
          <p class="text-sm text-white group-hover:text-white">New generation</p>
          <p class="text-xs text-gray-600 mt-0.5">Convert content into assets</p>
        </div>
        <span class="text-gray-600 group-hover:text-white transition-colors">&rarr;</span>
      </a>
    </div>

    <div>
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-medium text-white">Recent activity</h2>
      </div>

      {#if recentTasks.length === 0}
        <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-8 text-center">
          <p class="text-sm text-gray-600">No activity yet.</p>
        </div>
      {:else}
        <div class="space-y-0.5">
          {#each recentTasks as task}
            <a href="/tasks/{task.id}" class="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors hover:bg-[#111]">
              <span class="w-1.5 h-1.5 rounded-full shrink-0 {statusDot(task.status)}" />
              <span class="font-mono text-xs text-gray-600 w-16 shrink-0">{task.id.slice(0, 8)}</span>
              <span class="text-xs text-gray-500 flex-1 min-w-0 truncate">
                {task.status === "completed" ? "Assets generated" : task.status === "running" ? "Generating assets…" : task.status === "failed" ? "Generation failed" : "Queued"}
              </span>
              <span class="text-xs {statusClass(task.status)}">{task.status}</span>
              {#if task.created_at}
                <span class="text-xs text-gray-600 w-14 text-right shrink-0">{timeAgo(task.created_at)}</span>
              {/if}
            </a>
          {/each}
        </div>
      {/if}
    </div>
  </div>
{/if}
