<script lang="ts">
  import { onMount } from "svelte";
  import { Card } from "$lib/components/ui/card/index.js";
  import { Button } from "$lib/components/ui/button/index.js";
  import { API_BASE } from "$lib/api/config";

  let tokenSets = $state<{ id: string; name: string; version: number }[]>([]);
  let templates = $state<string[]>([]);
  let selectedToken = $state("");
  let selectedTemplate = $state("full-composite");
  let selectedFormat = $state("instagram-square");
  let singlePngUrl = $state("");
  let loading = $state(false);
  let error = $state("");

  // "Render All" state
  let renderAll = $state(false);
  let allResults = $state<{ name: string; url: string; dim: string }[]>([]);
  let allProgress = $state("");
  let allError = $state("");

  const FORMATS = [
    { id: "instagram-square", label: "Instagram Square", dim: "1080x1080" },
    { id: "instagram-portrait", label: "Instagram Portrait", dim: "1080x1350" },
    { id: "instagram-story", label: "Instagram Story", dim: "1080x1920" },
    { id: "linkedin-post", label: "LinkedIn Post", dim: "1200x627" },
    { id: "twitter-card", label: "X/Twitter", dim: "1200x675" },
    { id: "facebook-post", label: "Facebook Post", dim: "1200x630" },
    { id: "pinterest-pin", label: "Pinterest Pin", dim: "1000x1500" },
  ];

  onMount(async () => {
    const [tokensRes, templatesRes] = await Promise.all([
      fetch(`${API_BASE}/playground/token-list`).then(r => r.json()).catch(() => []),
      fetch(`${API_BASE}/playground/templates`).then(r => r.json()).catch(() => ({ templates: [] })),
    ]);
    tokenSets = tokensRes;
    templates = templatesRes.templates || [];
    if (tokenSets.length > 0) selectedToken = tokenSets[0].id;
  });

  async function renderPreview() {
    loading = true;
    error = "";
    singlePngUrl = "";
    try {
      const res = await fetch(`${API_BASE}/playground/render-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token_id: selectedToken || undefined,
          template_name: selectedTemplate,
          format_id: selectedFormat,
          render: true,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      singlePngUrl = URL.createObjectURL(blob);
    } catch (e) {
      error = e instanceof Error ? e.message : "Render failed";
    }
    finally { loading = false; }
  }

  async function renderAllTemplates() {
    renderAll = true;
    allResults = [];
    allError = "";
    allProgress = "";
    const toRender = templates.filter(t => !t.startsWith("llm-"));  // skip edge cases first pass

    for (let i = 0; i < toRender.length; i++) {
      allProgress = `Rendering ${toRender[i]} (${i + 1}/${toRender.length})…`;
      try {
        const res = await fetch(`${API_BASE}/playground/render-preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            token_id: selectedToken || undefined,
            template_name: toRender[i],
            format_id: selectedFormat,
            render: true,
          }),
        });
        if (!res.ok) {
          allResults = [...allResults, { name: toRender[i], url: "", dim: "ERROR" }];
          continue;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        allResults = [...allResults, { name: toRender[i], url, dim: FORMATS.find(f => f.id === selectedFormat)?.dim || selectedFormat }];
      } catch {
        allResults = [...allResults, { name: toRender[i], url: "", dim: "FAILED" }];
      }
    }
    allProgress = `Done — ${allResults.filter(r => r.url).length}/${toRender.length} rendered`;
  }

  async function renderEdgeCases() {
    renderAll = true;
    const edges = templates.filter(t => t.startsWith("llm-"));
    if (edges.length === 0) return;

    for (let i = 0; i < edges.length; i++) {
      allProgress = `Rendering edge case ${edges[i]} (${i + 1}/${edges.length})…`;
      try {
        const res = await fetch(`${API_BASE}/playground/render-preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            token_id: selectedToken || undefined,
            template_name: edges[i],
            format_id: selectedFormat,
            render: true,
          }),
        });
        if (!res.ok) {
          allResults = [...allResults, { name: edges[i], url: "", dim: "ERROR" }];
          continue;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        allResults = [...allResults, { name: edges[i], url, dim: FORMATS.find(f => f.id === selectedFormat)?.dim || selectedFormat }];
      } catch {
        allResults = [...allResults, { name: edges[i], url: "", dim: "FAILED" }];
      }
    }
    allProgress += ` | Edge cases: ${allResults.filter(r => r.url && r.name.startsWith("llm-")).length}/${edges.length}`;
  }

  function clearAll() {
    renderAll = false;
    allResults = [];
    allProgress = "";
    allError = "";
  }
</script>

<div class="max-w-7xl space-y-6">
  <div>
    <h1 class="text-lg font-medium text-text" style="font-family: var(--font-display)">Token Playground</h1>
    <p class="text-sm text-text-secondary mt-0.5">Test design token rendering across templates — no LLM calls.</p>
  </div>

  <Card class="p-5">
    <div class="flex flex-wrap items-end gap-4">
      <div>
        <label class="text-xs text-text-secondary block mb-1">Token Set</label>
        <select bind:value={selectedToken} class="h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none">
          <option value="">Default tokens (no brand)</option>
          {#each tokenSets as t}
            <option value={t.id}>{t.name} v{t.version}</option>
          {/each}
        </select>
      </div>
      <div>
        <label class="text-xs text-text-secondary block mb-1">Format</label>
        <select bind:value={selectedFormat} class="h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none">
          {#each FORMATS as f}
            <option value={f.id}>{f.label} ({f.dim})</option>
          {/each}
        </select>
      </div>
      {#if !renderAll}
        <div>
          <label class="text-xs text-text-secondary block mb-1">Single Template</label>
          <select bind:value={selectedTemplate} class="h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none">
            {#each templates as t}
              <option value={t}>{t}</option>
            {/each}
          </select>
        </div>
        <Button onclick={renderPreview} disabled={loading}>
          {loading ? "Rendering…" : "Render One"}
        </Button>
      {/if}
      {#if !renderAll}
        <Button onclick={renderAllTemplates} disabled={loading || templates.length === 0} variant="outline">
          Render All Templates
        </Button>
        <Button onclick={async () => { await renderAllTemplates(); await renderEdgeCases(); }} disabled={loading || templates.length === 0} variant="outline">
          Render All + Edge Cases
        </Button>
      {:else}
        <Button onclick={clearAll} variant="ghost">Clear Results</Button>
      {/if}
    </div>
  </Card>

  {#if error}
    <Card class="p-4"><p class="text-xs text-destructive">{error}</p></Card>
  {/if}

  {#if !renderAll && singlePngUrl}
    <Card class="overflow-hidden">
      <div class="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <span class="text-xs font-mono text-text-secondary">{selectedTemplate} @ {FORMATS.find(f => f.id === selectedFormat)?.dim || selectedFormat}</span>
        <a href={singlePngUrl} download="tasbir-preview.png" class="text-xs text-accent hover:text-accent/80 transition-colors">Download</a>
      </div>
      <div class="bg-bg flex items-center justify-center p-4 min-h-[200px]">
        <img src={singlePngUrl} alt="Rendered" class="max-w-full h-auto rounded-lg border border-border shadow-lg" style="max-height: 80vh" />
      </div>
    </Card>
    <Card class="p-3">
      <p class="text-xs text-text-secondary">✓ Rendered via Playwright with Tailwind CDN + design tokens</p>
    </Card>
  {/if}

  {#if renderAll}
    {#if allProgress}
      <p class="text-xs text-text-secondary">{allProgress}</p>
    {/if}

    {#if allResults.length > 0}
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {#each allResults as r}
          <Card class="overflow-hidden">
            <div class="px-3 py-2 border-b border-border flex items-center justify-between">
              <span class="text-xs font-mono text-text-secondary truncate">{r.name}</span>
              <span class="text-[10px] text-text-secondary shrink-0">{r.dim}</span>
            </div>
            <div class="bg-bg flex items-center justify-center min-h-[160px]">
              {#if r.url}
                <img src={r.url} alt={r.name} class="w-full h-auto" loading="lazy" />
              {:else}
                <span class="text-xs text-destructive">{r.dim}</span>
              {/if}
            </div>
          </Card>
        {/each}
      </div>

      <Card class="p-3">
        <p class="text-xs text-text-secondary">
          <span class="text-accent font-medium">{allResults.filter(r => r.url).length}</span> rendered successfully,
          <span class="text-destructive font-medium">{allResults.filter(r => !r.url).length}</span> failed.
          Check edge case templates (llm-*) for how the system handles unusual LLM output patterns.
        </p>
      </Card>
    {/if}
  {/if}

  {#if !renderAll && !singlePngUrl}
    <Card class="p-5">
      <p class="text-sm font-medium text-text mb-2">Available Templates</p>
      <div class="space-y-2 text-xs text-text-secondary">
        <p><span class="font-mono text-accent">full-composite</span> — Realistic social media card with all token categories</p>
        <p><span class="font-mono text-accent">color-palette</span> — Color swatches (bg-primary, bg-secondary, etc.)</p>
        <p><span class="font-mono text-accent">typography-scale</span> — All fonts and sizes</p>
        <p><span class="font-mono text-accent">glass-card</span> — Glassmorphism with backdrop-blur</p>
        <p><span class="font-mono text-accent">contrast-test</span> — Text contrast on all backgrounds</p>
        <p><span class="font-mono text-accent">spacing-layout</span> — Padding, gap, and radius</p>
        <p class="pt-2 font-medium text-destructive">Edge case templates (LLM output patterns):</p>
        <p><span class="font-mono text-warning">llm-output-sample</span> — Raw LLM output with Tailwind classes, no injection</p>
        <p><span class="font-mono text-warning">llm-glass-dark</span> — Dark glassmorphism card with Tailwind</p>
        <p><span class="font-mono text-warning">llm-two-column</span> — Horizontal two-column LinkedIn-style layout</p>
        <p><span class="font-mono text-warning">llm-bold-minimal</span> — Bold minimal poster, large typography</p>
        <p><span class="font-mono text-warning">llm-data-viz</span> — Data visualization with stats grid</p>
        <p><span class="font-mono text-warning">llm-mixed-styles</span> — Mixes Tailwind classes + inline styles</p>
        <p><span class="font-mono text-warning">llm-no-tailwind</span> — Pure inline CSS, no Tailwind at all (bad LLM output)</p>
      </div>
    </Card>
  {/if}
</div>
