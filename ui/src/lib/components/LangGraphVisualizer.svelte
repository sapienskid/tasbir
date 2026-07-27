<script lang="ts">
  import {
    SvelteFlow,
    Background,
    type Node,
    type Edge,
  } from "@xyflow/svelte";
  import PipelineNode from "./PipelineNode.svelte";
  import "@xyflow/svelte/dist/base.css";

  interface Props {
    activeNode?: string;
    progress?: number;
    qualityScore?: number;
    compact?: boolean;
    formatProgress?: Record<string, { stage: string; status: string; url?: string }>;
  }

  let {
    activeNode = "",
    progress = 0,
    qualityScore = 0,
    compact = false,
    formatProgress = {},
  }: Props = $props();

  function nodeStatus(nodeId: string): string {
    if (activeNode === "failed") return "failed";
    if (activeNode === "END" || progress >= 100) return "completed";
    if (activeNode === nodeId) return "active";
    const thresholds: Record<string, number> = {
      strategist: 10,
      copywriter: 25,
      visual_director: 40,
      designer: 55,
      quality_check: 72,
      renderer: 90,
    };
    return progress >= (thresholds[nodeId] ?? 100) ? "completed" : "pending";
  }

  const STATUS_COLORS: Record<string, string> = {
    pending: "#6b7280",
    active: "#a78bfa",
    completed: "#22c55e",
    failed: "#ef4444",
  };

  const NODE_LABELS: Record<string, { label: string; role: string }> = {
    strategist: { label: "Strategist", role: "Aura Vance" },
    copywriter: { label: "Copywriter", role: "Julian Sterling" },
    visual_director: { label: "Visual Director", role: "Elena Rostova" },
    designer: { label: "Designer", role: "Marcus Chen" },
    quality_check: { label: "Quality Check", role: "Victoria Thorne" },
    renderer: { label: "Renderer", role: "Playwright" },
  };

  const nodeTypes = {
    pipeline: PipelineNode,
  };

  function buildNodes(): Node[] {
    const ids = ["strategist", "copywriter", "visual_director", "designer", "quality_check", "renderer"];
    const gap = compact ? 180 : 220;
    const startX = 60;
    const y = 120;

    return ids.map((id, i) => {
      const status = nodeStatus(id);
      const info = NODE_LABELS[id];
      const color = STATUS_COLORS[status];

      const formatCount = Object.keys(formatProgress).length;
      const doneFormats = Object.values(formatProgress).filter((fp) => fp.status === "completed").length;
      const progressLabel = formatCount > 0 ? `${doneFormats}/${formatCount}` : "";

      return {
        id,
        type: "pipeline",
        position: { x: startX + i * gap, y },
        data: {
          status,
          color,
          nodeId: id,
          info,
          progressLabel,
          compact,
        },
        style: {
          background: status === "active"
            ? "rgba(167, 139, 250, 0.15)"
            : "var(--color-surface, #1e1e2e)",
          border: `2px solid ${color}`,
          borderRadius: "12px",
          padding: compact ? "8px 12px" : "12px 20px",
          width: compact ? "140px" : "170px",
          boxShadow: status === "active" ? `0 0 20px ${color}44` : "none",
          transition: "all 0.3s ease",
          opacity: status === "pending" ? 0.5 : 1,
        },
      };
    });
  }

  function buildEdges(): Edge[] {
    const ids = ["strategist", "copywriter", "visual_director", "designer", "quality_check", "renderer"];
    const edges: Edge[] = [];

    for (let i = 0; i < ids.length - 1; i++) {
      const srcStatus = nodeStatus(ids[i]);
      edges.push({
        id: `e-${ids[i]}-${ids[i + 1]}`,
        source: ids[i],
        target: ids[i + 1],
        type: "smoothstep",
        animated: srcStatus === "completed" || srcStatus === "active",
        style: {
          stroke: srcStatus === "completed" ? "#22c55e" : srcStatus === "active" ? "#a78bfa" : "#6b7280",
          strokeWidth: srcStatus === "completed" ? 2.5 : 1.5,
        },
      });
    }

    edges.push({
      id: "e-quality_check-designer-retry",
      source: "quality_check",
      target: "designer",
      type: "smoothstep",
      animated: true,
      style: {
        stroke: "#f59e0b",
        strokeWidth: 1.5,
        strokeDasharray: "5,5",
      },
      label: "↺ retry ≤2",
      labelStyle: { fill: "#f59e0b", fontSize: 10 },
    });

    return edges;
  }

  let nodes = $derived(buildNodes());
  let edges = $derived(buildEdges());
</script>

<div class="w-full bg-bg/50 rounded-xl border border-border p-4 transition-all">
  <div class="flex items-center justify-between mb-3">
    <div class="flex items-center gap-2">
      {#if activeNode && activeNode !== "END" && activeNode !== "failed"}
        <div class="w-2 h-2 rounded-full bg-accent animate-ping"></div>
      {:else}
        <div class="w-2 h-2 rounded-full bg-accent/30"></div>
      {/if}
      <span class="text-xs font-mono font-medium text-text uppercase tracking-wider">Pipeline</span>
    </div>
    {#if qualityScore > 0}
      <span class="text-xs text-text-secondary bg-accent/10 text-accent px-2 py-0.5 rounded-full font-mono">
        Score: {qualityScore}/100
      </span>
    {/if}
  </div>

  <div class="h-[300px]" class:compact-h={compact}>
    <SvelteFlow
      {nodes}
      {edges}
      {nodeTypes}
      fitView
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={false}
      zoomOnScroll={false}
      zoomOnPinch={false}
      zoomOnDoubleClick={false}
      preventScrolling={false}
    >
      <Background variant="dots" gap={20} size={1} />
    </SvelteFlow>
  </div>
</div>

<style>
  .compact-h {
    height: 220px;
  }

  :global(.svelte-flow__node) {
    font-family: inherit;
  }

  :global(.svelte-flow__edge-path) {
    transition: stroke 0.3s ease;
  }

  :global(.svelte-flow__node.selected),
  :global(.svelte-flow__node:focus) {
    outline: none;
    box-shadow: none;
  }
</style>
