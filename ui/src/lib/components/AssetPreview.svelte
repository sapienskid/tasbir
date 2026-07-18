<script lang="ts">
  let { src = "", format = "", alt = "" }: { src?: string; format?: string; alt?: string } = $props();
</script>

<div class="space-y-2">
  <div class="rounded-lg border overflow-hidden bg-gray-50 flex items-center justify-center" style="min-height: 200px">
    {#if src}
      <img {src} alt={alt || format} class="max-w-full h-auto" loading="lazy" />
    {:else}
      <p class="text-gray-400 text-sm">No preview available</p>
    {/if}
  </div>
  {#if format}
    <p class="text-xs text-gray-500 text-center">{format}</p>
  {/if}
</div>
