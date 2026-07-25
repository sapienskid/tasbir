<script lang="ts">
  import { onMount } from "svelte";
  import { Button } from "$lib/components/ui/button/index.js";
  import { api } from "$lib/api/client";

  const API_BASE = "http://localhost:8000";

  let brand = $state({
    name: "",
    tagline: "",
    story: "",
    tone: "professional",
    logo_url: "",
    primary_color: "#000000",
    secondary_color: "#666666",
  });
  let loading = $state(true);
  let saving = $state(false);
  let uploading = $state(false);
  let error = $state("");
  let success = $state("");

  const TONE_OPTIONS = [
    "professional", "playful", "luxury", "minimal", "energetic", "warm",
  ];

  onMount(async () => {
    try {
      const res = await fetch(`${API_BASE}/settings/brand`);
      if (res.ok) {
        const saved = await res.json();
        brand = { ...brand, ...saved };
      }
    } catch { /* use defaults */ }
    finally { loading = false; }
  });

  async function handleLogoUpload(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    uploading = true;
    error = "";
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/assets/upload`, { method: "POST", body: formData });
      const data = await res.json();
      brand.logo_url = `${API_BASE}${data.url}`;
    } catch (e) {
      error = "Upload failed";
    } finally { uploading = false; }
  }

  async function handleSave() {
    saving = true;
    error = "";
    success = "";
    try {
      await fetch(`${API_BASE}/settings/brand`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: brand }),
      });
      success = "Brand saved";
      setTimeout(() => success = "", 3000);
    } catch (e) {
      error = e instanceof Error ? e.message : "Save failed";
    } finally { saving = false; }
  }
</script>

<div class="p-8 max-w-3xl">
  <h1 class="text-lg font-medium text-white mb-1">Brand</h1>
  <p class="text-xs text-gray-600 mb-6">Configure your brand identity — agents use this to generate on-brand assets.</p>

  {#if loading}
    <div class="animate-pulse space-y-4">
      <div class="h-9 bg-[#111] rounded-lg" />
      <div class="h-24 bg-[#111] rounded-lg" />
    </div>
  {:else}
    <div class="space-y-4">
      <div class="rounded-xl border border-[#1c1c1c] bg-[#080808] p-5">
        <h2 class="text-sm font-medium text-white mb-4">Identity</h2>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-600 block mb-1">Brand name</label>
            <input bind:value={brand.name} class="w-full h-9 bg-black text-white text-sm rounded-lg border border-[#1c1c1c] px-3 focus:border-[#333] focus:outline-none" placeholder="Acme Corp" />
          </div>
          <div>
            <label class="text-xs text-gray-600 block mb-1">Tagline</label>
            <input bind:value={brand.tagline} class="w-full h-9 bg-black text-white text-sm rounded-lg border border-[#1c1c1c] px-3 focus:border-[#333] focus:outline-none" placeholder="Building the future" />
          </div>
          <div>
            <label class="text-xs text-gray-600 block mb-1">Brand story</label>
            <textarea bind:value={brand.story} rows={4} class="w-full bg-black text-white text-sm rounded-lg border border-[#1c1c1c] px-3 py-2 focus:border-[#333] focus:outline-none resize-none" placeholder="Tell the AI about your brand's mission, values, and voice…"></textarea>
          </div>
          <div>
            <label class="text-xs text-gray-600 block mb-1">Tone of voice</label>
            <div class="flex flex-wrap gap-2">
              {#each TONE_OPTIONS as t}
                <button
                  class="text-xs px-3 py-1.5 rounded-full border transition-all capitalize {brand.tone === t ? 'bg-white text-black border-white' : 'bg-transparent text-gray-600 border-[#1c1c1c] hover:border-gray-600'}"
                  onclick={() => brand.tone = t}
                >{t}</button>
              {/each}
            </div>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-[#1c1c1c] bg-[#080808] p-5">
        <h2 class="text-sm font-medium text-white mb-4">Colors</h2>
        <div class="flex gap-4">
          <div class="flex-1">
            <label class="text-xs text-gray-600 block mb-1">Primary</label>
            <div class="flex gap-2 items-center">
              <input type="color" bind:value={brand.primary_color} class="w-8 h-8 rounded border-0 cursor-pointer bg-transparent" />
              <input bind:value={brand.primary_color} class="flex-1 h-9 bg-black text-white text-xs rounded-lg border border-[#1c1c1c] px-3 font-mono focus:border-[#333] focus:outline-none" />
            </div>
          </div>
          <div class="flex-1">
            <label class="text-xs text-gray-600 block mb-1">Secondary</label>
            <div class="flex gap-2 items-center">
              <input type="color" bind:value={brand.secondary_color} class="w-8 h-8 rounded border-0 cursor-pointer bg-transparent" />
              <input bind:value={brand.secondary_color} class="flex-1 h-9 bg-black text-white text-xs rounded-lg border border-[#1c1c1c] px-3 font-mono focus:border-[#333] focus:outline-none" />
            </div>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-[#1c1c1c] bg-[#080808] p-5">
        <h2 class="text-sm font-medium text-white mb-4">Logo</h2>
        <div class="flex items-start gap-4">
          <div class="w-24 h-24 rounded-xl border border-[#1c1c1c] bg-black flex items-center justify-center overflow-hidden shrink-0">
            {#if brand.logo_url}
              <img src={brand.logo_url} alt="Logo" class="w-full h-full object-contain" />
            {:else}
              <span class="text-[10px] text-gray-600">No logo</span>
            {/if}
          </div>
          <div class="flex-1">
            <label class="text-xs text-gray-600 block mb-2">Upload logo (PNG, SVG)</label>
            <input type="file" accept="image/png,image/svg+xml,image/jpeg" onchange={handleLogoUpload} class="text-xs text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:bg-white file:text-black file:font-medium hover:file:cursor-pointer" />
            {#if uploading}
              <p class="text-xs text-gray-600 mt-1">Uploading…</p>
            {/if}
          </div>
        </div>
      </div>

      {#if error}
        <p class="text-xs text-red-500/70">{error}</p>
      {/if}
      {#if success}
        <p class="text-xs text-white">{success}</p>
      {/if}

      <div class="flex justify-end pt-2">
        <Button variant="default" disabled={saving} onclick={handleSave}>
          {saving ? "Saving…" : "Save brand"}
        </Button>
      </div>
    </div>
  {/if}
</div>
