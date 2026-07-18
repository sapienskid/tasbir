<script lang="ts">
  import { cn } from "$lib/utils";

  let {
    class: className = "",
    variant = "default",
    ...rest
  }: {
    class?: string;
    variant?: "default" | "textarea";
    [key: string]: unknown;
  } = $props();

  const base =
    "w-full bg-surface text-white font-body transition-all placeholder:text-gray-600 focus:outline-none";
</script>

{#if variant === "textarea"}
  <textarea
    class={cn(
      base,
      "min-h-[160px] resize-y rounded-lg border border-border px-4 py-3 text-sm leading-relaxed focus:border-border-focus",
      className
    )}
    {...rest}
  ></textarea>
{:else}
  <input
    class={cn(
      base,
      "h-10 rounded-lg border border-border px-4 text-sm focus:border-border-focus",
      className
    )}
    {...rest}
  />
{/if}
