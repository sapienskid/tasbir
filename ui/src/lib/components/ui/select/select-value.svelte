<script lang="ts">
  import { Select as SelectPrimitive } from "bits-ui";

  let {
    ref = $bindable(null),
    placeholder = "Select an option",
    ...restProps
  }: SelectPrimitive.ValueProps = $props();
</script>

<SelectPrimitive.Value bind:ref {placeholder} {...restProps}>
  {#snippet children({ selected })}
    {#if selected?.label}
      {selected.label}
    {:else}
      {placeholder}
    {/if}
  {/snippet}
</SelectPrimitive.Value>
