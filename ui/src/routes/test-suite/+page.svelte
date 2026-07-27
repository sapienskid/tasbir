<script lang="ts">
  import { onMount } from "svelte";
  import { Card } from "$lib/components/ui/card/index.js";
  import { Button } from "$lib/components/ui/button/index.js";
  import { API_BASE } from "$lib/api/config";

  let tokenSets = $state<{ id: string; name: string }[]>([]);
  let templates = $state<string[]>([]);
  let selectedFormat = $state("instagram-square");
  let running = $state(false);
  let progress = $state("");
  let error = $state("");

  // Results
  let runId = $state("");
  let results = $state<any[]>([]);
  let summary = $state({ total: 0, successful: 0, failed: 0 });

  // Past runs
  let pastRuns = $state<any[]>([]);
  let viewingRun = $state("");

  const FORMATS = [
    { id: "instagram-square", label: "Instagram Square", dim: "1080x1080" },
    { id: "instagram-portrait", label: "Instagram Portrait", dim: "1080x1350" },
    { id: "linkedin-post", label: "LinkedIn Post", dim: "1200x627" },
    { id: "twitter-card", label: "X/Twitter", dim: "1200x675" },
  ];

  onMount(async () => {
    const [tokensRes, templatesRes, runsRes] = await Promise.all([
      fetch(`${API_BASE}/playground/token-list`).then(r => r.json()).catch(() => []),
      fetch(`${API_BASE}/playground/templates`).then(r => r.json()).catch(() => ({ templates: [] })),
      fetch(`${API_BASE}/playground/test-suite/runs`).then(r => r.json()).catch(() => ({ runs: [] })),
    ]);
    tokenSets = tokensRes;
    templates = templatesRes.templates || [];
    pastRuns = runsRes.runs || [];
  });

  async function runSuite() {
    running = true;
    error = "";
    results = [];
    progress = "Starting test suite…";
    runId = "";

    try {
      const res = await fetch(`${API_BASE}/playground/test-suite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format_id: selectedFormat }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      runId = data.run_id;
      results = data.results;
      summary = { total: data.total, successful: data.successful, failed: data.failed };
      progress = `Completed — ${data.successful}/${data.total} passed`;
      // Refresh past runs
      const runsRes = await fetch(`${API_BASE}/playground/test-suite/runs`).then(r => r.json()).catch(() => ({ runs: [] }));
      pastRuns = runsRes.runs || [];
    } catch (e) {
      error = e instanceof Error ? e.message : "Suite failed";
    }
    finally { running = false; }
  }

  async function loadRun(id: string) {
    viewingRun = id;
    runId = "";
    results = [];
    try {
      const res = await fetch(`${API_BASE}/playground/test-suite/${id}`);
      if (!res.ok) throw new Error("Cannot load run");
      const data = await res.json();
      runId = data.run_id;
      results = data.results;
      summary = { total: data.total, successful: data.successful, failed: data.failed };
    } catch { viewingRun = ""; }
  }

  function groupedResults() {
    const groups: Record<string, { token: string; items: any[] }> = {};
    for (const r of results) {
      const key = r.token_name;
      if (!groups[key]) groups[key] = { token: key, items: [] };
      groups[key].items.push(r);
    }
    return Object.values(groups);
  }

  function statusClass(r: any) {
    if (r.success) return "border-accent/30";
    if (r.error?.includes("None")) return "border-yellow-500/30";
    return "border-destructive/30";
  }

  function timeAgo(ts: string) {
    if (!ts) return "";
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
  }
</script>

<div class="max-w-7xl space-y-6">
  <div>
    <h1 class="text-lg font-medium text-text" style="font-family: var(--font-display)">Visual Test Suite</h1>
    <p class="text-sm text-text-secondary mt-0.5">
      Loops through all token sets × all templates to verify design token injection.
      Saves HTML + PNG for each combination — inspect saved HTML to debug what went wrong.
    </p>
  </div>

  <!-- Controls -->
  <Card class="p-5">
    <div class="flex flex-wrap items-end gap-4">
      <div>
        <label class="text-xs text-text-secondary block mb-1">Format</label>
        <select bind:value={selectedFormat} class="h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none">
          {#each FORMATS as f}
            <option value={f.id}>{f.label} ({f.dim})</option>
          {/each}
        </select>
      </div>
      <div>
        <p class="text-xs text-text-secondary mb-1">{tokenSets.length + 1} token sets × {templates.length} templates = <span class="text-accent font-medium">{(tokenSets.length + 1) * templates.length} tests</span></p>
      </div>
      <Button onclick={runSuite} disabled={running || templates.length === 0}>
        {running ? "Running…" : "Run Full Test Suite"}
      </Button>
    </div>
  </Card>

  {#if progress}
    <Card class="p-3">
      <p class="text-xs text-text-secondary">{progress}</p>
    </Card>
  {/if}

  {#if error}
    <Card class="p-3"><p class="text-xs text-destructive">{error}</p></Card>
  {/if}

  <!-- Results grid -->
  {#if runId && results.length > 0}
    <Card class="p-4">
      <div class="flex items-center justify-between mb-3">
        <div>
          <span class="text-xs font-mono text-text-secondary">Run: {runId}</span>
          <span class="ml-3 text-xs text-text-secondary">
            <span class="text-accent">{summary.successful}</span> passed · 
            <span class="text-destructive">{summary.failed}</span> failed · 
            {summary.total} total
          </span>
        </div>
      </div>

      {#each groupedResults() as group}
        <div class="mb-4">
          <h3 class="text-xs font-medium text-text mb-2">{group.token}</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {#each group.items as r}
              <div class="rounded-lg border {statusClass(r)} bg-bg overflow-hidden">
                <div class="bg-surface px-2 py-1 border-b border-border flex items-center justify-between">
                  <span class="text-[10px] font-mono text-text-secondary truncate">{r.template}</span>
                  <span class="text-[9px] {r.success ? 'text-accent' : 'text-destructive'}">{r.success ? '✓' : '✗'}</span>
                </div>
                {#if r.png_url}
                  <img src="{API_BASE}{r.png_url}" alt={r.template} class="w-full h-auto" loading="lazy" />
                {:else}
                  <div class="p-4 text-center">
                    <p class="text-[10px] text-destructive">{r.error || "No render"}</p>
                  </div>
                {/if}
                <div class="px-2 py-1 border-t border-border flex gap-2">
                  {#if r.html_url}
                    <a href="{API_BASE}{r.html_url}" target="_blank" class="text-[9px] text-text-secondary hover:text-accent">HTML</a>
                  {/if}
                  {#if r.png_url}
                    <a href="{API_BASE}{r.png_url}" target="_blank" class="text-[9px] text-text-secondary hover:text-accent">PNG</a>
                  {/if}
                  {#if r.html_size}
                    <span class="text-[9px] text-text-secondary ml-auto">{r.html_size > 1024 ? (r.html_size/1024).toFixed(0)+'KB' : r.html_size+'B'}</span>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </Card>

    <Card class="p-3">
      <p class="text-xs text-text-secondary">
        <span class="text-accent">Green border</span> = render succeeded · 
        <span class="text-yellow-500">Yellow</span> = HTML generated but PNG failed (Playwright issue) · 
        <span class="text-destructive">Red</span> = crash/error
        <br>
        Click <span class="font-mono text-accent">HTML</span> to inspect the injected source — verify Tailwind CDN, CSS vars, and Google Fonts are present.
        If the HTML has proper injection but the PNG looks wrong, the issue is in how Tailwind resolves the classes.
      </p>
    </Card>
  {/if}

  <!-- Past runs -->
  {#if pastRuns.length > 0}
    <Card class="p-5">
      <h2 class="text-sm font-medium text-text mb-3">Previous Runs</h2>
      <div class="space-y-1">
        {#each pastRuns as run}
          <button
            onclick={() => loadRun(run.run_id)}
            class="w-full text-left flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-elevated transition-colors {viewingRun === run.run_id ? 'bg-elevated border border-border' : ''}"
          >
            <span class="text-xs font-mono text-text-secondary">{run.run_id}</span>
            <span class="text-xs text-text-secondary">{run.format}</span>
            <span class="text-xs text-accent">{run.successful}/{run.total}</span>
            {#if run.failed > 0}
              <span class="text-xs text-destructive">{run.failed} failed</span>
            {/if}
            <span class="text-xs text-text-secondary ml-auto">{timeAgo(run.timestamp)}</span>
          </button>
        {/each}
      </div>
    </Card>
  {/if}
</div>
