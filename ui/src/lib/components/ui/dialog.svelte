<script lang="ts">
  import { cn } from "$lib/utils";

  let {
    open = false,
    onclose,
    title = "",
    children,
  }: {
    open?: boolean;
    onclose?: () => void;
    title?: string;
    children?: import("svelte").Snippet;
  } = $props();

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") onclose?.();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <div class="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
    <div class="fixed inset-0 bg-black/80" onclick={onclose} role="presentation"></div>
    <div
      class={cn(
        "relative z-10 w-full max-w-sm rounded-xl border border-border bg-surface p-6 shadow-2xl",
        "animate-[fadeIn_0.2s_ease-out]"
      )}
    >
      {#if title}
        <div class="flex items-center justify-between mb-5">
          <h2 class="text-sm font-medium text-white">{title}</h2>
          <button class="text-gray-500 hover:text-white text-lg leading-none" onclick={onclose}>✕</button>
        </div>
      {/if}
      {#if children}
        {@render children()}
      {/if}
    </div>
  </div>
{/if}

<style>
  :global(.animate-\[fadeIn_0\.2s_ease-out\]) {
    animation: fadeIn 0.2s ease-out;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-8px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
</style>
