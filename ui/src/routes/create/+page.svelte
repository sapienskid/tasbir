<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { Button } from "$lib/components/ui/button/index.js";
  import { startGeneration, getTask, type TaskResult } from "$lib/api/generate";
  import { listFormats } from "$lib/api/formats";
  import { listTokens, type DesignToken } from "$lib/api/tokens";
  import { Card } from "$lib/components/ui/card/index.js";
  import { Select, SelectTrigger, SelectContent, SelectItem } from "$lib/components/ui/select/index.js";

  const API_BASE = "http://localhost:8000";

  const AGENTS = ["Strategist", "Copywriter", "Visual Director", "Designer", "Quality Check", "Renderer"];
  const STAGES = ["queued", "analyzing", "writing", "designing", "rendering", "complete"];

  let content = $state("");
  let formats = $state<{ id: string; label: string; dim: string; w: number; h: number }[]>([]);
  let selectedFormats = $state<string[]>([]);
  let generating = $state(false);
  let error = $state("");
  let focused = $state(false);
  let loading = $state(true);

  let taskId = $state("");
  let status = $state("");
  let progress = $state(0);
  let activeStage = $state(-1);
  let assets = $state<Record<string, string>>({});
  let qualityScore = $state(0);
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  let tokens = $state<DesignToken[]>([]);
  let selectedTokenId = $state("");

  onMount(async () => {
    try {
      const [apiFormats, tok] = await Promise.all([
        listFormats(),
        listTokens().catch(() => []),
      ]);
      formats = apiFormats.map((f: any) => ({ id: f.id, label: f.name, dim: `${f.width}x${f.height}`, w: f.width, h: f.height }));
      selectedFormats = formats.length > 0 ? [formats[0].id] : [];
      tokens = tok;
    } catch {
      formats = [
        { id: "instagram-square", label: "Instagram Square", dim: "1080x1080", w: 1080, h: 1080 },
        { id: "instagram-portrait", label: "Instagram Portrait", dim: "1080x1350", w: 1080, h: 1350 },
        { id: "instagram-story", label: "Instagram Story", dim: "1080x1920", w: 1080, h: 1920 },
        { id: "linkedin-post", label: "LinkedIn", dim: "1200x627", w: 1200, h: 627 },
        { id: "twitter-card", label: "X / Twitter", dim: "1200x675", w: 1200, h: 675 },
        { id: "facebook-post", label: "Facebook", dim: "1200x630", w: 1200, h: 630 },
        { id: "pinterest-pin", label: "Pinterest", dim: "1000x1500", w: 1000, h: 1500 },
      ];
      selectedFormats = ["instagram-square"];
    } finally { loading = false; }
  });

  onDestroy(() => { if (pollTimer) clearInterval(pollTimer); });

  function toggleFormat(id: string) {
    selectedFormats = selectedFormats.includes(id)
      ? selectedFormats.filter((f) => f !== id)
      : [...selectedFormats, id];
  }

  function assetUrl(url: string): string {
    if (url.startsWith("/")) return `${API_BASE}${url}`;
    return url;
  }

  function getActiveStage(): number {
    if (progress < 10) return 0;
    if (progress < 30) return 1;
    if (progress < 50) return 2;
    if (progress < 70) return 3;
    if (progress < 90) return 4;
    return 5;
  }

  async function handleGenerate() {
    if (!content.trim() || selectedFormats.length === 0) return;
    generating = true;
    error = "";
    status = "starting";
    progress = 0;
    activeStage = 0;
    assets = {};
    qualityScore = 0;

    try {
      const tokenData = selectedTokenId
        ? (tokens.find(t => t.id === selectedTokenId)?.data || {})
        : {};

      const res = await startGeneration({
        content,
        title: content.split("\n")[0].slice(0, 100),
        requested_formats: selectedFormats,
        ...(selectedTokenId ? { design_tokens: tokenData } : {}),
      });
      taskId = res.task_id;

      pollTimer = setInterval(async () => {
        try {
          const data = await getTask(taskId);
          status = data.status;
          progress = data.progress || 0;
          activeStage = getActiveStage();

          if (data.status === "completed") {
            if (pollTimer) clearInterval(pollTimer);
            if (data.result?.assets_by_format) {
              const raw = data.result.assets_by_format as Record<string, string>;
              for (const [k, v] of Object.entries(raw)) raw[k] = assetUrl(v);
              assets = raw;
            }
            qualityScore = data.result?.quality_score || 0;
            generating = false;
          } else if (data.status === "failed") {
            if (pollTimer) clearInterval(pollTimer);
            error = data.error || "Generation failed";
            generating = false;
          }
        } catch { /* poll continues */ }
      }, 2000);
    } catch (e) {
      error = e instanceof Error ? e.message : "Could not start generation";
      generating = false;
    }
  }
</script>

<div class="max-w-6xl space-y-6">
  <div>
    <h1 class="text-lg font-medium text-text" style="font-family: var(--font-display)">Create</h1>
    <p class="text-sm text-text-secondary mt-0.5">Describe your content, pick formats, and generate social media assets.</p>
  </div>

  {#if status !== "completed"}
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <!-- Left: input -->
      <div class="lg:col-span-3 space-y-4">
        <Card class="p-5">
          <div class="scan-border rounded-xl" class:is-active={focused}>
            <textarea
              bind:value={content}
              onfocus={() => (focused = true)}
              onblur={() => (focused = false)}
              rows={6}
              class="w-full bg-bg text-text text-sm leading-relaxed rounded-xl border border-border px-4 py-3 placeholder:text-text-secondary/40 focus:outline-none resize-none transition-colors"
              placeholder="Paste a blog post, article, or notes…"
            ></textarea>
          </div>

          {#if tokens.length > 0}
            <div class="mt-4">
              <label class="text-xs text-text-secondary block mb-1.5">Design tokens (optional)</label>
              <Select bind:value={selectedTokenId}>
                <SelectTrigger class="w-56">
                  <span class="text-text-secondary">Auto-generate from vibe</span>
                </SelectTrigger>
                <SelectContent>
                  {#each tokens as t}
                    <SelectItem value={t.id}>{t.name}</SelectItem>
                  {/each}
                </SelectContent>
              </Select>
            </div>
          {/if}

          {#if error}
            <p class="mt-3 text-xs text-destructive">{error}</p>
          {/if}

          <div class="mt-4 flex items-center gap-3">
            <Button
              disabled={generating || !content.trim() || selectedFormats.length === 0}
              onclick={handleGenerate}
              variant={content.trim() && selectedFormats.length > 0 ? "accent" : "primary"}
              size="md"
            >
              {generating ? `${progress}%` : "Generate"}
            </Button>
            {#if !content.trim()}
              <span class="text-xs text-text-secondary">Paste content to get started</span>
            {:else if selectedFormats.length === 0}
              <span class="text-xs text-text-secondary">Select at least one format</span>
            {/if}
          </div>
        </Card>

        {#if generating}
          <Card class="p-5">
            <p class="text-xs text-text-secondary mb-3">Progress</p>
            <div class="w-full h-1.5 bg-border rounded-full overflow-hidden mb-4">
              <div class="h-full bg-accent rounded-full transition-all duration-500" style="width: {progress}%" />
            </div>
            <div class="flex items-center gap-0 overflow-x-auto">
              {#each AGENTS as agent, i}
                <div class="flex items-center shrink-0">
                  <div class="flex flex-col items-center gap-1.5" class:opacity-30={i > activeStage}>
                    <div class="w-1.5 h-1.5 rounded-full {i <= activeStage ? 'bg-accent' : 'bg-border'}" />
                    <span class="text-[10px] text-text-secondary whitespace-nowrap">{agent}</span>
                  </div>
                  {#if i < AGENTS.length - 1}
                    <div class="w-8 sm:w-12 h-px bg-border mx-1.5" class:bg-accent={i < activeStage} />
                  {/if}
                </div>
              {/each}
            </div>
          </Card>
        {/if}
      </div>

      <!-- Right: format selection -->
      <div class="lg:col-span-2">
        <Card class="p-5">
          <p class="text-xs text-text-secondary mb-3">Formats</p>
          {#if loading}
            <div class="grid grid-cols-2 gap-2">
              {#each [1,2,3,4] as _}
                <div class="h-16 bg-surface rounded-xl animate-pulse" />
              {/each}
            </div>
          {:else}
            <div class="grid grid-cols-2 gap-2">
              {#each formats as fmt}
                <button
                  onclick={() => toggleFormat(fmt.id)}
                  class="text-left rounded-xl border p-3 transition-all {selectedFormats.includes(fmt.id) ? 'border-accent bg-accent/10' : 'border-border bg-bg hover:border-border-focus'}"
                >
                  <p class="text-xs text-text font-medium mb-0.5">{fmt.label}</p>
                  <p class="text-[10px] text-text-secondary">{fmt.dim}</p>
                </button>
              {/each}
            </div>
          {/if}
        </Card>
      </div>
    </div>
  {/if}

  <!-- Results -->
  {#if Object.keys(assets).length > 0}
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-sm font-medium text-text">Generated assets</h2>
          <p class="text-xs text-text-secondary mt-0.5">Quality score: {qualityScore}/100</p>
        </div>
        <Button variant="ghost" size="sm" onclick={() => { status = ""; assets = {}; content = ""; }}>
          New generation
        </Button>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {#each Object.entries(assets) as [fmt, url]}
          <Card class="overflow-hidden">
            <div class="px-4 py-2.5 border-b border-border flex items-center justify-between">
              <span class="text-xs font-mono text-text-secondary">{fmt}</span>
              <a href={url} target="_blank" class="text-xs text-text-secondary hover:text-accent transition-colors">open</a>
            </div>
            <div class="bg-bg flex items-center justify-center min-h-[280px]">
              <img src={url} alt={fmt} class="max-w-full h-auto" loading="lazy" />
            </div>
          </Card>
        {/each}
      </div>
    </div>
  {/if}
</div>
