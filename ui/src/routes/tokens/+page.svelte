<script lang="ts">
  import { onMount } from "svelte";
  import Button from "$lib/components/ui/button.svelte";
  import { listTokens, generateTokens, deleteToken, type DesignToken } from "$lib/api/tokens";

  let tokens = $state<DesignToken[]>([]);
  let loading = $state(true);
  let error = $state("");
  let brandName = $state("");
  let generating = $state(false);

  onMount(async () => {
    try { tokens = await listTokens(); }
    catch (e) { error = "Failed to load tokens"; }
    finally { loading = false; }
  });

  async function handleGenerate() {
    if (!brandName.trim()) return;
    generating = true;
    error = "";
    try {
      const token = await generateTokens(brandName);
      tokens = [token, ...tokens];
      brandName = "";
    } catch (e) {
      error = e instanceof Error ? e.message : "Generation failed";
    } finally { generating = false; }
  }

  async function handleDelete(id: string) {
    try {
      await deleteToken(id);
      tokens = tokens.filter((t) => t.id !== id);
    } catch {}
  }
</script>

<div class="p-8 max-w-2xl">
  <h1 class="text-lg font-medium text-white mb-6">Design tokens</h1>

  <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-4 mb-6">
    <p class="text-xs text-gray-600 mb-3">Generate DTCG-format design tokens from a brand name. Includes colors, typography, and spacing.</p>
    <div class="flex gap-2">
      <input
        bind:value={brandName}
        class="flex-1 h-9 bg-black text-white text-sm rounded-lg border border-[#1c1c1c] px-3 focus:border-[#333] focus:outline-none"
        placeholder="Brand name (e.g. Acme Corp)"
      />
      <Button variant="primary" size="sm" disabled={generating || !brandName.trim()} onclick={handleGenerate}>
        {generating ? "…" : "Generate"}
      </Button>
    </div>
    {#if error}
      <p class="text-xs text-gray-600 mt-2">{error}</p>
    {/if}
  </div>

  {#if loading}
    <p class="text-sm text-gray-600">Loading…</p>
  {:else if tokens.length === 0}
    <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-8 text-center">
      <p class="text-sm text-gray-600">No design tokens yet.</p>
    </div>
  {:else}
    <div class="space-y-1.5">
      {#each tokens as token}
        <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-4">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span class="text-sm text-white">{token.name}</span>
              <span class="text-xs text-gray-600">v{token.version}</span>
              <span class="text-xs text-gray-600">{token.source}</span>
            </div>
            <Button variant="ghost" size="sm" onclick={() => handleDelete(token.id)}>delete</Button>
          </div>
          <pre class="text-xs text-gray-600 overflow-x-auto font-mono max-h-32 leading-relaxed">{JSON.stringify(token.data, null, 1)}</pre>
        </div>
      {/each}
    </div>
  {/if}
</div>
