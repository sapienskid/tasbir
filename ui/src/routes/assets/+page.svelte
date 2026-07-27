<script lang="ts">
  import { onMount } from "svelte";
  import Confirm from "$lib/components/ui/confirm.svelte";
  import { listTasks } from "$lib/api/generate";
  import { Card } from "$lib/components/ui/card/index.js";
  import { Button } from "$lib/components/ui/button/index.js";
  import LangGraphVisualizer from "$lib/components/LangGraphVisualizer.svelte";
  import { activeTask } from "$lib/stores/activeTask";
  import { API_BASE } from "$lib/api/config";

  interface AssetGroup {
    id: string;
    title: string;
    created_at: string;
    assets: Record<string, string>;
  }

  let groups = $state<AssetGroup[]>([]);
  let loading = $state(true);
  let deleting = $state<string | null>(null);
  let confirmDelete = $state<string | null>(null);

  function assetUrl(url: string): string {
    if (url.startsWith("/")) return `${API_BASE}${url}`;
    return url;
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

  onMount(async () => {
    try {
      const tasks = await listTasks(100);
      const active = tasks.filter((t) => t.status === "completed" || t.status === "running");

      const results = await Promise.all(active.map(async (t) => {
        try {
          const res = await fetch(`${API_BASE}/tasks/${t.id}`);
          const detail = await res.json();
          const rawAssets = detail?.result?.assets_by_format || {};
          const assets: Record<string, string> = {};
          for (const [k, v] of Object.entries(rawAssets)) {
            assets[k] = v as string;
          }
          if (Object.keys(assets).length === 0) return null;
          return { id: t.id, title: t.title || t.id.slice(0, 10), created_at: t.created_at, assets };
        } catch { return null; }
      }));

      groups = results.filter(Boolean) as AssetGroup[];
    } catch { /* empty */ }
    finally { loading = false; }
  });

  async function handleDelete(id: string) {
    deleting = id;
    try {
      await fetch(`${API_BASE}/tasks/${id}`, { method: "DELETE" });
      groups = groups.filter(g => g.id !== id);
    } catch { /* ignore */ }
    finally { deleting = null; }
  }

  let allFormats = $derived([...new Set(groups.flatMap(g => Object.keys(g.assets)))]);
  let formatFilter = $state("");

  let filtered = $derived(
    formatFilter ? groups.filter(g => Object.keys(g.assets).includes(formatFilter)) : groups
  );
</script>

<div class="max-w-6xl space-y-6">
  <div class="flex items-start justify-between gap-4 flex-wrap">
    <div>
      <h1 class="text-lg font-medium text-text" style="font-family: var(--font-display)">Assets</h1>
      <p class="text-sm text-text-secondary mt-0.5">{groups.length} generations with assets</p>
    </div>
    {#if allFormats.length > 0}
      <div class="flex gap-1.5 flex-wrap">
        <button
          class="text-xs px-3 py-1 rounded-full border transition-colors {!formatFilter ? 'bg-accent text-white border-accent' : 'bg-transparent text-text-secondary border-border hover:border-border-focus'}"
          onclick={() => formatFilter = ""}
        >All</button>
        {#each allFormats as f}
          <button
            class="text-xs px-3 py-1 rounded-full border transition-colors {formatFilter === f ? 'bg-accent text-white border-accent' : 'bg-transparent text-text-secondary border-border hover:border-border-focus'}"
            onclick={() => formatFilter = f}
          >{f}</button>
        {/each}
      </div>
    {/if}
  </div>

  {#if $activeTask.taskId && $activeTask.status === "running"}
    <Card class="p-4">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-blue-500 animate-ping"></span>
          <span class="text-sm text-text">Active: {$activeTask.title || $activeTask.taskId.slice(0, 8)}</span>
        </div>
        <span class="text-xs font-mono text-text-secondary">{$activeTask.progress}%</span>
      </div>
      <LangGraphVisualizer activeNode={$activeTask.activeNode} progress={$activeTask.progress} compact />
    </Card>
  {/if}

  {#if loading}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each [1,2,3] as _}
        <div class="h-48 bg-surface rounded-xl animate-pulse"></div>
      {/each}
    </div>
  {:else if filtered.length === 0}
    <Card class="p-8 text-center">
      <p class="text-sm text-text-secondary">No assets yet. Generate something first.</p>
    </Card>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each filtered as group}
        <Card class="overflow-hidden hover:border-border-focus transition-colors">
          <div class="flex items-center justify-between px-4 py-3 border-b border-border">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-sm text-text font-medium truncate">{group.title}</span>
              <span class="text-[11px] text-text-secondary shrink-0">{timeAgo(group.created_at)}</span>
            </div>
            <button onclick={() => confirmDelete = group.id} disabled={deleting === group.id} class="text-xs text-text-secondary hover:text-destructive transition-colors shrink-0">
              {deleting === group.id ? "..." : "Delete"}
            </button>
          </div>
          <div class="p-3">
            <div class="grid grid-cols-2 gap-2">
              {#each Object.entries(group.assets) as [fmt, url]}
                <a href={assetUrl(url)} target="_blank" class="block rounded-lg border border-border bg-bg overflow-hidden hover:border-accent/50 transition-colors group">
                  <div class="aspect-square bg-bg flex items-center justify-center overflow-hidden">
                    <img src={assetUrl(url)} alt={fmt} class="w-full h-full object-cover" loading="lazy" />
                  </div>
                  <div class="px-2 py-1.5 border-t border-border flex items-center justify-between">
                    <span class="text-[10px] text-text-secondary font-mono truncate">{fmt}</span>
                  </div>
                </a>
              {/each}
            </div>
          </div>
          <div class="px-4 py-2 border-t border-border">
            <a href="/tasks/{group.id}" class="text-xs text-text-secondary hover:text-accent transition-colors">Details</a>
          </div>
        </Card>
      {/each}
    </div>
  {/if}
</div>

<Confirm
  open={confirmDelete !== null}
  title="Delete generation"
  message="Delete this generation and all its assets? This cannot be undone."
  confirmLabel="Delete"
  variant="destructive"
  onconfirm={() => { const id = confirmDelete; confirmDelete = null; if (id) handleDelete(id); }}
  oncancel={() => confirmDelete = null}
/>
