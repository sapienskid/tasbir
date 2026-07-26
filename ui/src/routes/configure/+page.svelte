<script lang="ts">
  import { onMount } from "svelte";
  import Confirm from "$lib/components/ui/confirm.svelte";
  import { Button } from "$lib/components/ui/button/index.js";
  import { Card } from "$lib/components/ui/card/index.js";
  import { Select, SelectTrigger, SelectContent, SelectItem } from "$lib/components/ui/select/index.js";
  import TokenPreview from "$lib/components/TokenPreview.svelte";
  import { apiKey } from "$lib/stores/auth";
  import { api } from "$lib/api/client";
  import { listTokens, generateTokens, deleteToken, type DesignToken } from "$lib/api/tokens";

  const API_BASE = "http://localhost:8000";

  // Tab state
  type Tab = "general" | "brand" | "formats" | "prompts";
  let activeTab = $state<Tab>("general");

  function setTab(t: Tab) {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", t);
    history.replaceState({}, "", url.toString());
    activeTab = t;
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: "general", label: "General" },
    { id: "brand", label: "Brand & Tokens" },
    { id: "formats", label: "Formats" },
    { id: "prompts", label: "Prompts" },
  ];

  // ── API Key (always visible) ──
  let keyInput = $state("");

  // ── Brand & Tokens tab ──
  let brandLoading = $state(true);
  let tokens = $state<DesignToken[]>([]);
  let generating = $state(false);
  let brandError = $state("");
  let brandSuccess = $state("");

  let brandName = $state("");
  let brandStory = $state("");
  let tone = $state("professional");
  let primaryColor = $state("#000000");
  let secondaryColor = $state("#666666");
  let activePreview = $state<string | null>(null);

  const TONES = ["professional", "playful", "luxury", "minimal", "energetic", "warm", "serious"];

  // ── Formats tab ──
  let fmtLoading = $state(true);
  let formats = $state<any[]>([]);
  let fmtError = $state("");
  let fmtSaving = $state(false);

  let fmtEditing = $state<string | null>(null);
  let formId = $state("");
  let formName = $state("");
  let formWidth = $state(1080);
  let formHeight = $state(1080);
  let formInstruction = $state("");

  let confirmTokenDelete = $state<string | null>(null);
  let confirmFormatDelete = $state<string | null>(null);

  // ── Prompts tab ──
  let promptsLoading = $state(true);
  let prompts = $state<{ name: string; system_prompt: string; temperature: number; max_tokens: number; user_template: string | null; version: number }[]>([]);
  let promptsEditing = $state<string | null>(null);
  let editPrompt = $state("");
  let editTemp = $state(0.7);
  let editTokensVal = $state(2000);
  let promptsSaving = $state(false);
  let promptsError = $state("");

  const AGENT_COLORS: Record<string, string> = {
    strategist: "#CD5B7D",
    copywriter: "#5B7D7C",
    visual_director: "#9B9BA0",
    designer: "#CD5B7D",
    quality_check: "#5B7D7C",
    token_generator: "#9B9BA0",
  };

  // ── Init ──
  onMount(async () => {
    keyInput = $apiKey;
    const params = new URL(window.location.href).searchParams;
    const tabParam = params.get("tab") as Tab | null;
    if (tabParam && TABS.some(t => t.id === tabParam)) {
      activeTab = tabParam;
    }
    await Promise.all([loadBrand(), loadFormats(), loadPrompts()]);
  });

  function saveKey() {
    apiKey.setKey(keyInput);
  }

  // ── Brand ──
  async function loadBrand() {
    brandLoading = true;
    try {
      const [brandRes, tokList] = await Promise.all([
        fetch(`${API_BASE}/settings/brand`).then(r => r.json()).catch(() => ({})),
        listTokens().catch(() => []),
      ]);
      tokens = tokList;
      if (brandRes.name) brandName = brandRes.name;
      if (brandRes.story) brandStory = brandRes.story;
      if (brandRes.tone) tone = brandRes.tone;
      if (brandRes.primary_color) primaryColor = brandRes.primary_color;
      if (brandRes.secondary_color) secondaryColor = brandRes.secondary_color;
      for (const t of tokens) activePreview = t.id;
    } catch {} finally { brandLoading = false; }
  }

  async function handleGenerateTokens() {
    if (!brandName.trim()) return;
    generating = true;
    brandError = "";
    brandSuccess = "";
    try {
      const token = await generateTokens(brandName, {
        tone, style: "modern",
        primary_color: primaryColor || undefined,
        secondary_color: secondaryColor || undefined,
      });

      await fetch(`${API_BASE}/settings/brand`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: { name: brandName, story: brandStory, tone, primary_color: primaryColor, secondary_color: secondaryColor } }),
      });

      tokens = [token, ...tokens];
      activePreview = token.id;
      brandSuccess = "Tokens generated and brand saved";
      setTimeout(() => brandSuccess = "", 3000);
    } catch (e) {
      brandError = e instanceof Error ? e.message : "Generation failed";
    } finally { generating = false; }
  }

  async function handleDeleteToken(id: string) {
    try {
      await deleteToken(id);
      tokens = tokens.filter((t) => t.id !== id);
    } catch { /* ignore */ }
  }

  // ── Formats ──
  async function loadFormats() {
    fmtLoading = true;
    try {
      const res = await fetch(`${API_BASE}/formats?enabled_only=false`);
      formats = await res.json();
    } catch { fmtError = "Failed to load formats"; }
    finally { fmtLoading = false; }
  }

  function startFormatCreate() {
    fmtEditing = "__new__";
    formId = "";
    formName = "";
    formWidth = 1080;
    formHeight = 1080;
    formInstruction = "";
    fmtError = "";
  }

  function startFormatEdit(f: any) {
    fmtEditing = f.id;
    formId = f.id;
    formName = f.name;
    formWidth = f.width;
    formHeight = f.height;
    formInstruction = f.ai_instruction || "";
    fmtError = "";
  }

  function cancelFormatForm() { fmtEditing = null; formId = ""; }

  async function saveFormat() {
    if (!formId.trim() || !formName.trim()) return;
    fmtSaving = true;
    fmtError = "";
    try {
      const body = { name: formName, width: formWidth, height: formHeight, ai_instruction: formInstruction };
      if (fmtEditing === "__new__") {
        await api.post("/formats", { id: formId, ...body });
      } else {
        await api.put(`/formats/${fmtEditing}`, body);
      }
      const res = await fetch(`${API_BASE}/formats?enabled_only=false`);
      formats = await res.json();
      cancelFormatForm();
    } catch (e) {
      fmtError = e instanceof Error ? e.message : "Save failed";
    } finally { fmtSaving = false; }
  }

  async function deleteFormat(id: string) {
    try {
      await api.delete(`/formats/${id}`);
      formats = formats.filter(f => f.id !== id);
    } catch { /* ignore */ }
  }

  // ── Prompts ──
  async function loadPrompts() {
    promptsLoading = true;
    try {
      const res = await fetch(`${API_BASE}/prompts`);
      prompts = await res.json();
    } catch { promptsError = "Failed to load prompts"; }
    finally { promptsLoading = false; }
  }

  function startPromptEdit(name: string) {
    const p = prompts.find(p => p.name === name);
    if (!p) return;
    promptsEditing = name;
    editPrompt = p.system_prompt;
    editTemp = p.temperature;
    editTokensVal = p.max_tokens;
    promptsError = "";
  }

  async function savePromptEdit() {
    if (!promptsEditing) return;
    promptsSaving = true;
    promptsError = "";
    try {
      const res = await fetch(`${API_BASE}/prompts/${promptsEditing}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ system_prompt: editPrompt, temperature: editTemp, max_tokens: editTokensVal }),
      });
      if (!res.ok) throw new Error("Save failed");
      const updated = await res.json();
      prompts = prompts.map(p => p.name === promptsEditing ? updated : p);
      promptsEditing = null;
    } catch (e) {
      promptsError = e instanceof Error ? e.message : "Failed to save";
    } finally { promptsSaving = false; }
  }
</script>

<div class="max-w-6xl space-y-6">
  <div>
    <h1 class="text-lg font-medium text-text" style="font-family: var(--font-display)">Configure</h1>
    <p class="text-sm text-text-secondary mt-0.5">Brand identity, formats, agent prompts, and app settings.</p>
  </div>

  <!-- Tab bar -->
  <div class="flex gap-1 border-b border-border pb-px overflow-x-auto">
    {#each TABS as tab}
      <button
        class="text-sm px-4 py-2.5 transition-colors shrink-0 {activeTab === tab.id ? 'text-accent border-b-2 border-accent' : 'text-text-secondary hover:text-text'}"
        onclick={() => setTab(tab.id)}
      >
        {tab.label}
      </button>
    {/each}
  </div>

  <!-- ── General ── -->
  {#if activeTab === "general"}
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div class="lg:col-span-3 space-y-4">
        <Card class="p-5">
          <h2 class="text-sm font-medium text-text mb-1">API Key</h2>
          <p class="text-xs text-text-secondary mb-3">Your key for authenticating with the Tasbir backend.</p>
          <div class="flex gap-2">
            <input
              bind:value={keyInput}
              class="flex-1 h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none font-mono"
              placeholder="sk-…"
            />
            <Button variant="default" size="sm" onclick={saveKey}>Save</Button>
          </div>
        </Card>

        <Card class="p-5">
          <h2 class="text-sm font-medium text-text mb-1">Pipeline</h2>
          <p class="text-xs text-text-secondary mb-3">Control how the generation pipeline behaves.</p>
          <div class="space-y-4">
            <div>
              <label class="text-xs text-text-secondary block mb-1">Pipeline timeout (seconds)</label>
              <input type="number" value="300" disabled class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none opacity-40" />
              <p class="text-[10px] text-text-secondary mt-1">Configured server-side. Restart worker to apply changes.</p>
            </div>
            <div>
              <label class="text-xs text-text-secondary block mb-1">Quality threshold</label>
              <input type="number" value="50" disabled class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none opacity-40" />
              <p class="text-[10px] text-text-secondary mt-1">Minimum quality score for generated assets (0-100). Set in backend config.</p>
            </div>
          </div>
        </Card>
      </div>

      <div class="lg:col-span-2 space-y-4">
        <Card class="p-5">
          <h2 class="text-sm font-medium text-text mb-1">Logging</h2>
          <p class="text-xs text-text-secondary mb-3">Server logging level.</p>
          <div>
            <label class="text-xs text-text-secondary block mb-1">Log level</label>
            <select class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none appearance-none opacity-40" disabled>
              <option>info</option>
              <option>debug</option>
              <option>warning</option>
              <option>error</option>
            </select>
            <p class="text-[10px] text-text-secondary mt-1">Set via LOG_LEVEL in .env file.</p>
          </div>
        </Card>

        <Card class="p-5">
          <h2 class="text-sm font-medium text-text mb-1">Rate limiting</h2>
          <p class="text-xs text-text-secondary mb-3">API rate limiting.</p>
          <div class="space-y-3">
            <div>
              <label class="text-xs text-text-secondary block mb-1">Status</label>
              <select class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none appearance-none opacity-40" disabled>
                <option>Disabled</option>
              </select>
              <p class="text-[10px] text-text-secondary mt-1">Set via RATE_LIMIT_ENABLED in .env.</p>
            </div>
          </div>
        </Card>
      </div>
    </div>

  <!-- ── Brand & Tokens ── -->
  {:else if activeTab === "brand"}
    <Card class="p-5">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <div>
          <label class="text-xs text-text-secondary block mb-1">Brand name</label>
          <input bind:value={brandName} class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none" placeholder="Acme Corp" />
        </div>
        <div>
          <label class="text-xs text-text-secondary block mb-1">Tone</label>
          <Select bind:value={tone}>
            <SelectTrigger>
              <span class="text-text-secondary">Select tone</span>
            </SelectTrigger>
            <SelectContent>
              {#each TONES as t}
                <SelectItem value={t}>{t}</SelectItem>
              {/each}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label class="text-xs text-text-secondary block mb-1">Primary</label>
          <div class="flex gap-2 items-center">
            <input type="color" bind:value={primaryColor} class="h-9 w-9 rounded-lg border border-border cursor-pointer bg-transparent" />
            <input bind:value={primaryColor} class="flex-1 h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 font-mono focus:border-border-focus focus:outline-none" />
          </div>
        </div>
        <div>
          <label class="text-xs text-text-secondary block mb-1">Secondary</label>
          <div class="flex gap-2 items-center">
            <input type="color" bind:value={secondaryColor} class="h-9 w-9 rounded-lg border border-border cursor-pointer bg-transparent" />
            <input bind:value={secondaryColor} class="flex-1 h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 font-mono focus:border-border-focus focus:outline-none" />
          </div>
        </div>
      </div>
      <div class="flex gap-2 items-end">
        <div class="flex-1">
          <label class="text-xs text-text-secondary block mb-1">Brand story (AI context)</label>
          <input bind:value={brandStory} class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none" placeholder="Your brand's mission, values, and voice…" />
        </div>
        <Button variant="default" size="sm" disabled={generating || !brandName.trim()} onclick={handleGenerateTokens}>
          {generating ? "Setting up…" : "Setup brand"}
        </Button>
      </div>
      {#if brandError}
        <p class="text-xs text-destructive mt-2">{brandError}</p>
      {/if}
      {#if brandSuccess}
        <p class="text-xs text-accent mt-2">{brandSuccess}</p>
      {/if}
    </Card>

    <!-- Token list -->
    <div class="space-y-3">
      {#if brandLoading}
        <p class="text-sm text-text-secondary">Loading…</p>
      {:else if tokens.length === 0}
        <Card class="p-8 text-center">
          <p class="text-sm text-text-secondary">No brand setup yet. Fill in your brand details above.</p>
        </Card>
      {:else}
        {#each tokens as token (token.id)}
          <Card class="overflow-hidden">
            <div class="flex items-center justify-between px-5 py-3.5 border-b border-border">
              <div class="flex items-center gap-3">
                <span class="text-sm text-text font-medium capitalize">{token.name}</span>
                <span class="text-[11px] py-0.5 px-2 rounded bg-bg text-text-secondary">v{token.version}</span>
                <span class="text-[11px] py-0.5 px-2 rounded bg-bg text-text-secondary">{token.source}</span>
              </div>
              <Button variant="ghost" size="sm" onclick={() => confirmTokenDelete = token.id}>Delete</Button>
            </div>
            <details class="group" open={activePreview === token.id}>
              <summary class="px-5 py-3 text-xs text-text-secondary cursor-pointer hover:text-text transition-colors select-none">
                {activePreview === token.id ? "Hide preview" : "Show preview"}
              </summary>
              <div class="px-5 pb-5">
                <TokenPreview data={token.data} tokenId={token.id} />
              </div>
            </details>
          </Card>
        {/each}
      {/if}
    </div>

  <!-- ── Formats ── -->
  {:else if activeTab === "formats"}
    <div class="flex items-center justify-between">
      <p class="text-xs text-text-secondary">Each format has dimensions and a narrative the AI uses when generating copy and design.</p>
      <Button variant="default" size="sm" onclick={startFormatCreate}>New format</Button>
    </div>

    {#if fmtEditing !== null}
      <Card class="p-5">
        <h2 class="text-sm font-medium text-text mb-4">{fmtEditing === "__new__" ? "New format" : "Edit format"}</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label class="text-xs text-text-secondary block mb-1">ID</label>
            <input bind:value={formId} disabled={fmtEditing !== "__new__"} class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none {fmtEditing !== '__new__' ? 'opacity-40' : ''}" placeholder="instagram-square" />
          </div>
          <div>
            <label class="text-xs text-text-secondary block mb-1">Name</label>
            <input bind:value={formName} class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none" placeholder="Instagram Square" />
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label class="text-xs text-text-secondary block mb-1">Width (px)</label>
            <input type="number" bind:value={formWidth} class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none" />
          </div>
          <div>
            <label class="text-xs text-text-secondary block mb-1">Height (px)</label>
            <input type="number" bind:value={formHeight} class="w-full h-9 bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none" />
          </div>
        </div>
        <div>
          <label class="text-xs text-text-secondary block mb-1.5">AI narrative</label>
          <textarea bind:value={formInstruction} rows={3} class="w-full bg-bg text-text text-xs rounded-xl border border-border px-3 py-2 focus:border-border-focus focus:outline-none resize-none" placeholder="Square format for Instagram feed. Bold visual, minimal text overlay."></textarea>
        </div>
        {#if fmtError}
          <p class="text-xs text-destructive mt-2">{fmtError}</p>
        {/if}
        <div class="flex gap-2 mt-3">
          <Button variant="default" size="sm" disabled={fmtSaving} onclick={saveFormat}>{fmtSaving ? "Saving…" : "Save"}</Button>
          <Button variant="ghost" size="sm" onclick={cancelFormatForm}>Cancel</Button>
        </div>
      </Card>
    {/if}

    {#if fmtLoading}
      <p class="text-sm text-text-secondary">Loading…</p>
    {:else if formats.length === 0 && fmtEditing === null}
      <Card class="p-8 text-center">
        <p class="text-sm text-text-secondary">No formats yet.</p>
      </Card>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each formats as f}
          <Card class="overflow-hidden">
            <div class="px-5 py-3.5 flex items-center justify-between">
              <div class="flex items-center gap-3">
                <span class="text-sm text-text font-medium">{f.name}</span>
                <span class="text-[11px] text-text-secondary font-mono">{f.width}x{f.height}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-[10px] text-text-secondary">{f.enabled ? "active" : "disabled"}</span>
                <button onclick={() => startFormatEdit(f)} class="text-xs text-text-secondary hover:text-text transition-colors">Edit</button>
                <button onclick={() => confirmFormatDelete = f.id} class="text-xs text-text-secondary hover:text-destructive transition-colors">Delete</button>
              </div>
            </div>
            {#if f.ai_instruction}
              <div class="px-5 pb-3.5 border-t border-border pt-3">
                <p class="text-xs text-text-secondary italic">{f.ai_instruction}</p>
              </div>
            {/if}
          </Card>
        {/each}
      </div>
    {/if}

  <!-- ── Prompts ── -->
  {:else if activeTab === "prompts"}
    {#if promptsError}
      <p class="text-xs text-destructive">{promptsError}</p>
    {/if}

    {#if promptsLoading}
      <p class="text-sm text-text-secondary">Loading…</p>
    {:else}
      <div class="space-y-3">
        {#each prompts as p}
          {@const color = AGENT_COLORS[p.name] || "#666"}
          <Card class="overflow-hidden">
            <button
              class="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-elevated transition-colors"
              onclick={() => startPromptEdit(p.name)}
            >
              <div class="w-2 h-2 rounded-full shrink-0" style="background:{color}"></div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm text-text font-medium capitalize">{p.name.replace("_", " ")}</span>
                  <span class="text-[10px] text-text-secondary bg-bg px-1.5 py-0.5 rounded font-mono">{p.name}</span>
                  <span class="text-[10px] text-text-secondary">v{p.version}</span>
                </div>
                <p class="text-xs text-text-secondary truncate mt-0.5">{p.system_prompt.slice(0, 120)}…</p>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <span class="text-[10px] text-text-secondary">{p.temperature} temp</span>
                <span class="text-[10px] text-text-secondary">{p.max_tokens} tok</span>
                <span class="text-text-secondary text-sm">{promptsEditing === p.name ? "−" : "✎"}</span>
              </div>
            </button>

            {#if promptsEditing === p.name}
              <div class="px-5 pb-4 border-t border-border pt-4">
                <label class="text-xs text-text-secondary block mb-1.5">System prompt</label>
                <textarea
                  bind:value={editPrompt}
                  rows={6}
                  class="w-full bg-bg text-text text-xs leading-relaxed rounded-xl border border-border px-3 py-2 focus:border-border-focus focus:outline-none resize-none font-mono"
                ></textarea>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
                  <div>
                    <label class="text-xs text-text-secondary block mb-1">Temperature</label>
                    <div class="flex items-center gap-2">
                      <input type="range" min="0" max="1" step="0.1" bind:value={editTemp} class="flex-1 accent-accent" />
                      <span class="text-xs text-text-secondary font-mono w-8">{editTemp}</span>
                    </div>
                  </div>
                  <div>
                    <label class="text-xs text-text-secondary block mb-1">Max tokens</label>
                    <input type="number" bind:value={editTokensVal} class="h-8 w-full bg-bg text-text text-xs rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none" />
                  </div>
                </div>

                <div class="flex gap-2 mt-3">
                  <Button variant="default" size="sm" disabled={promptsSaving} onclick={savePromptEdit}>
                    {promptsSaving ? "Saving…" : "Save"}
                  </Button>
                  <Button variant="ghost" size="sm" onclick={() => promptsEditing = null}>Cancel</Button>
                </div>
              </div>
            {/if}
          </Card>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<Confirm
  open={confirmTokenDelete !== null}
  title="Delete token"
  message="Delete this design token set? This cannot be undone."
  confirmLabel="Delete"
  variant="destructive"
  onconfirm={() => { const id = confirmTokenDelete; confirmTokenDelete = null; if (id) handleDeleteToken(id); }}
  oncancel={() => confirmTokenDelete = null}
/>

<Confirm
  open={confirmFormatDelete !== null}
  title="Delete format"
  message="Delete this format? This cannot be undone."
  confirmLabel="Delete"
  variant="destructive"
  onconfirm={() => { const id = confirmFormatDelete; confirmFormatDelete = null; if (id) deleteFormat(id); }}
  oncancel={() => confirmFormatDelete = null}
/>
