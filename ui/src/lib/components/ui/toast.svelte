<script lang="ts">
  import { cn } from "$lib/utils";
  import { createEventDispatcher } from "svelte";

  let {
    message = "",
    type: toastType = "info",
    visible = false,
  }: { message?: string; type?: "info" | "success" | "error"; visible?: boolean } = $props();

  const dispatch = createEventDispatcher();

  const colors: Record<string, string> = {
    info: "bg-blue-50 text-blue-800 border-blue-200",
    success: "bg-green-50 text-green-800 border-green-200",
    error: "bg-red-50 text-red-800 border-red-200",
  };
</script>

{#if visible}
  <div
    class={cn(
      "fixed bottom-4 right-4 z-50 flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg transition-all",
      colors[toastType]
    )}
  >
    <span class="text-sm">{message}</span>
    <button class="ml-2 text-sm font-medium opacity-70 hover:opacity-100" onclick={() => dispatch("close")}>
      ✕
    </button>
  </div>
{/if}
