<script lang="ts">
  let { formats = [], selected = [], onToggle }: {
    formats?: { id: string; name: string; width: number; height: number }[];
    selected?: string[];
    onToggle?: (formatId: string) => void;
  } = $props();
</script>

<div class="grid grid-cols-2 md:grid-cols-3 gap-3">
  {#each formats as fmt}
    <button
      class="rounded-lg border p-3 text-left transition-all {selected.includes(fmt.id) ? 'border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600' : 'border-gray-200 hover:border-gray-300'}"
      onclick={() => onToggle?.(fmt.id)}
    >
      <div class="font-medium text-sm">{fmt.name}</div>
      <div class="text-xs text-gray-500 mt-1">
        {fmt.width} × {fmt.height}
      </div>
    </button>
  {/each}
</div>
