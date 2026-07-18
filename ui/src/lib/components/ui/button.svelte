<script lang="ts">
  import { cn } from "$lib/utils";

  let {
    variant = "primary",
    size = "md",
    disabled = false,
    class: className = "",
    children,
    ...rest
  }: {
    variant?: "primary" | "secondary" | "ghost";
    size?: "sm" | "md" | "lg";
    disabled?: boolean;
    class?: string;
    children?: import("svelte").Snippet;
    [key: string]: unknown;
  } = $props();

  const base =
    "inline-flex items-center justify-center whitespace-nowrap font-body font-medium transition-all select-none";

  const variants: Record<string, string> = {
    primary:
      "bg-white text-black hover:bg-white/90 active:bg-white/80",
    secondary:
      "bg-elevated text-white border border-border hover:border-border-focus active:bg-elevated/80",
    ghost: "text-gray-400 hover:text-white hover:bg-elevated",
  };

  const sizes: Record<string, string> = {
    sm: "h-8 px-3 text-xs",
    md: "h-10 px-5 text-sm",
    lg: "h-12 px-7 text-base",
  };
</script>

<button
  class={cn(base, variants[variant], sizes[size], disabled && "opacity-40 pointer-events-none", className)}
  {disabled}
  {...rest}
>
  {#if children}
    {@render children()}
  {/if}
</button>
