<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import Button from "$lib/components/ui/button.svelte";
  import { startGeneration } from "$lib/api/generate";
  import { listFormats } from "$lib/api/formats";

  let content = $state("");
  let formats = $state<{ id: string; label: string; dim: string }[]>([]);
  let selectedFormats = $state<string[]>([]);
  let generating = $state(false);
  let error = $state("");
  let focused = $state(false);
  let loading = $state(true);

  onMount(async () => {
    try {
      const apiFormats = await listFormats();
      formats = apiFormats.map((f) => ({ id: f.id, label: f.name, dim: `${f.width}×${f.height}` }));
      selectedFormats = formats.length > 0 ? [formats[0].id] : [];
    } catch {
      formats = [
        { id: "instagram-square", label: "Instagram", dim: "1080×1080" },
        { id: "instagram-story", label: "Story", dim: "1080×1920" },
        { id: "linkedin", label: "LinkedIn", dim: "1200×627" },
        { id: "twitter", label: "X / Twitter", dim: "1200×675" },
        { id: "facebook", label: "Facebook", dim: "1200×630" },
        { id: "pinterest", label: "Pinterest", dim: "1000×1500" },
      ];
      selectedFormats = ["instagram-square"];
    } finally { loading = false; }
  });

  function toggleFormat(id: string) {
    selectedFormats = selectedFormats.includes(id)
      ? selectedFormats.filter((f) => f !== id)
      : [...selectedFormats, id];
  }

  async function handleGenerate() {
    if (!content.trim() || selectedFormats.length === 0) return;
    generating = true;
    error = "";
    try {
      const res = await startGeneration({ content, title: content.split("\n")[0].slice(0, 100), requested_formats: selectedFormats });
      goto(`/tasks/${res.task_id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : "Could not start generation";
    } finally { generating = false; }
  }
</script>

<div class="p-8 max-w-2xl">
  <h1 class="text-lg font-medium text-white mb-1">Generate assets</h1>
  <p class="text-sm text-gray-600 mb-6">Paste your content, pick your formats, and generate.</p>

  <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-5">
    <div class="scan-border rounded-lg" class:is-active={focused}>
      <textarea
        bind:value={content}
        onfocus={() => (focused = true)}
        onblur={() => (focused = false)}
        rows={6}
        class="w-full bg-black text-white text-sm leading-relaxed rounded-lg border border-[#1c1c1c] px-4 py-3 placeholder:text-[#555] focus:outline-none resize-none transition-colors"
        placeholder="Paste a blog post, article, or notes…"
      ></textarea>
    </div>

    <div class="mt-4">
      <p class="text-xs text-gray-600 mb-2">Formats</p>
      {#if loading}
        <div class="flex gap-2">
          {#each [1,2,3] as _}
            <span class="block h-7 w-24 rounded-full bg-[#111] animate-pulse" />
          {/each}
        </div>
      {:else}
        <div class="flex flex-wrap gap-2">
          {#each formats as fmt}
            <button
              class="text-xs px-3 py-1.5 rounded-full border transition-all {selectedFormats.includes(fmt.id) ? 'bg-white text-black border-white' : 'bg-transparent text-gray-600 border-[#1c1c1c] hover:border-gray-600 hover:text-gray-400'}"
              onclick={() => toggleFormat(fmt.id)}
            >
              {fmt.label} <span class="opacity-50">{fmt.dim}</span>
            </button>
          {/each}
        </div>
      {/if}
    </div>

    {#if error}
      <p class="mt-3 text-xs text-gray-600">{error}</p>
    {/if}

    <div class="mt-4 flex items-center gap-3">
      <Button
        disabled={generating || !content.trim() || selectedFormats.length === 0}
        onclick={handleGenerate}
        variant="primary"
        size="md"
      >
        {generating ? "Starting…" : "Generate"}
      </Button>
      {#if !content.trim()}
        <span class="text-xs text-gray-600">Paste content to get started</span>
      {:else if selectedFormats.length === 0}
        <span class="text-xs text-gray-600">Select at least one format</span>
      {/if}
    </div>
  </div>
</div>
