<script lang="ts">
  import type { NodeProps } from "@xyflow/svelte";

  type NodeData = {
    status: string;
    color: string;
    nodeId: string;
    info: { label: string; role: string };
    progressLabel: string;
    compact: boolean;
  };

  let { data }: NodeProps = $props();
  let d = $derived(data as unknown as NodeData);
</script>

<div class="flex flex-col items-center justify-center text-center gap-0.5 w-full">
  <span class="text-[11px] font-semibold leading-tight" style="color: {d.color}">
    {d.info.label}
  </span>
  {#if !d.compact}
    <span class="text-[9px] opacity-60 truncate max-w-[130px]">
      {d.info.role}
    </span>
  {/if}
  {#if d.status === "active"}
    <span class="text-[9px] font-mono mt-0.5" style="color: {d.color}">
      executing...
    </span>
  {:else if d.status === "completed"}
    <span class="text-[9px] font-mono mt-0.5" style="color: {d.color}">
      ✓ done
    </span>
  {/if}
  {#if d.progressLabel}
    <span class="text-[8px] font-mono mt-0.5 px-1.5 py-0.5 rounded-full bg-accent/10 text-accent">
      {d.progressLabel}
    </span>
  {/if}
</div>
