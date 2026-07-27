<script lang="ts">
  interface Props {
    activeNode?: string;
    progress?: number;
    qualityScore?: number;
    compact?: boolean;
  }

  let { activeNode = "", progress = 0, qualityScore = 0, compact = false }: Props = $props();

  interface GraphNode {
    id: string;
    label: string;
    role: string;
    minProgress: number;
  }

  const NODES: GraphNode[] = [
    { id: "strategist", label: "Strategist", role: "Aura Vance", minProgress: 10 },
    { id: "copywriter", label: "Copywriter", role: "Julian Sterling", minProgress: 30 },
    { id: "visual_director", label: "Visual Director", role: "Elena Rostova", minProgress: 50 },
    { id: "designer", label: "Designer", role: "Marcus Chen", minProgress: 70 },
    { id: "quality_check", label: "Quality Check", role: "Victoria Thorne", minProgress: 85 },
    { id: "renderer", label: "Renderer", role: "Playwright", minProgress: 95 },
  ];

  function getNodeState(nodeId: string, nodeMinProgress: number): "completed" | "active" | "pending" | "failed" {
    if (activeNode === "failed") return "failed";
    if (activeNode === "END" || progress >= 100) return "completed";
    if (activeNode === nodeId) return "active";
    if (progress >= nodeMinProgress) return "completed";
    return "pending";
  }
</script>

<div class="w-full bg-bg/50 rounded-xl border border-border p-4 transition-all">
  <div class="flex items-center justify-between mb-3">
    <div class="flex items-center gap-2">
      <div class="w-2 h-2 rounded-full bg-accent animate-ping"></div>
      <span class="text-xs font-mono font-medium text-text uppercase tracking-wider">LangGraph Execution Pipeline</span>
    </div>
    {#if qualityScore > 0}
      <span class="text-xs text-text-secondary bg-accent/10 text-accent px-2 py-0.5 rounded-full font-mono">
        Audit Score: {qualityScore}/100
      </span>
    {/if}
  </div>

  <!-- Graph Nodes and Edges -->
  <div class="flex items-center justify-between gap-1 overflow-x-auto py-2">
    <!-- Entry Point -->
    <div class="flex items-center gap-1 shrink-0">
      <div class="px-2 py-1 rounded bg-surface border border-border text-[10px] font-mono text-text-secondary">
        START
      </div>
      <div class="w-4 h-px bg-border"></div>
    </div>

    {#each NODES as node, index}
      {@const state = getNodeState(node.id, node.minProgress)}
      <div class="flex items-center gap-1 shrink-0">
        <!-- Node Box -->
        <div
          class="relative flex flex-col items-center justify-center rounded-lg border px-3 py-2 transition-all duration-300 min-w-[90px]
          {state === 'active' ? 'border-accent bg-accent/15 shadow-sm shadow-accent/20 ring-2 ring-accent/30 scale-105' : ''}
          {state === 'completed' ? 'border-border bg-surface text-text' : ''}
          {state === 'pending' ? 'border-border/40 bg-surface/30 opacity-50' : ''}
          {state === 'failed' ? 'border-destructive bg-destructive/10 text-destructive' : ''}"
        >
          {#if state === 'active'}
            <span class="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-accent"></span>
            </span>
          {/if}

          <span class="text-[11px] font-medium text-text leading-tight text-center">{node.label}</span>
          {#if !compact}
            <span class="text-[9px] text-text-secondary/70 mt-0.5 text-center truncate max-w-[85px]">{node.role}</span>
          {/if}

          {#if state === 'completed'}
            <span class="text-[9px] text-accent font-mono mt-0.5">✓ done</span>
          {:else if state === 'active'}
            <span class="text-[9px] text-accent font-mono mt-0.5 animate-pulse">executing...</span>
          {/if}
        </div>

        <!-- Edge connector with feedback loop branch on Quality Check -->
        {#if index < NODES.length - 1}
          <div class="relative flex items-center px-1">
            <div class="w-6 h-px {state === 'completed' ? 'bg-accent' : 'bg-border'}"></div>
            {#if node.id === 'quality_check'}
              <!-- Conditional Refinement Loop indicator -->
              <div class="absolute -bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1 text-[8px] text-text-secondary/60">
                <span>↺ retry &le;2</span>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}

    <!-- END Node -->
    <div class="flex items-center gap-1 shrink-0">
      <div class="w-4 h-px {progress >= 100 ? 'bg-accent' : 'bg-border'}"></div>
      <div
        class="px-2 py-1 rounded border text-[10px] font-mono transition-colors
        {progress >= 100 ? 'bg-accent text-white border-accent' : 'bg-surface border-border text-text-secondary'}"
      >
        END
      </div>
    </div>
  </div>
</div>
