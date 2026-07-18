<script lang="ts">
  import { cn } from "$lib/utils";

  let {
    class: className = "",
    children,
    ...rest
  }: { class?: string; children?: import("svelte").Snippet; [key: string]: unknown } = $props();
</script>

<select
  class={cn(
    "flex h-9 w-full rounded-md border border-gray-300 bg-white px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-600 disabled:cursor-not-allowed disabled:opacity-50",
    className
  )}
  {...rest}
>
  {#if children}
    {@render children()}
  {/if}
</select>
