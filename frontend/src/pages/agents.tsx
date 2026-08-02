import { lazy, Suspense, useMemo, useState } from "react"
import dagre from "@dagrejs/dagre"
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  MarkerType,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { ArrowRight, Activity } from "lucide-react"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { useAgentGraph, useAgents } from "@/hooks/use-library"
import {
  getTaskProgress,
  listModels,
  listTasks,
  promptPreview,
  resetAgent,
  updateAgent,
  type AgentConfig,
  type AgentGraphSpec,
  type ModelInfo,
  type PromptPreview,
  type TaskProgress,
} from "@/lib/api"
import { useTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"

const NODE_WIDTH = 220
const NODE_HEIGHT = 88

const HANDLE_CLS = "!h-2.5 !w-2.5 !border-0 !bg-border"

type FlowNodeData = {
  label: string
  kind: string
  persona?: string
  model?: string
  state?: "done" | "running" | "pending"
}
type FlowNode = Node<FlowNodeData>

function layoutNodes(nodes: FlowNode[], edges: Edge[]): FlowNode[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: "LR", nodesep: 48, ranksep: 72 })
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }))
  edges.forEach((e) => g.setEdge(e.source, e.target))
  dagre.layout(g)
  return nodes.map((n) => {
    const pos = g.node(n.id)
    return {
      ...n,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      // Explicit size: React Flow routes edges from these bounds immediately
      // (no waiting on DOM measurement), so connections always render.
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      style: { width: NODE_WIDTH, height: NODE_HEIGHT },
    }
  })
}

function buildGraph(spec: AgentGraphSpec): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes: FlowNode[] = spec.nodes.map((n) => ({
    id: n.id,
    type: n.kind === "agent" ? "agent" : n.kind === "group" ? "group" : "term",
    position: { x: 0, y: 0 },
    data: { label: n.label, kind: n.kind, persona: n.persona, model: n.model },
  }))
  const edges: Edge[] = spec.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    type: "smoothstep",
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
    style: { strokeWidth: 2.5 },
  }))
  return { nodes: layoutNodes(nodes, edges), edges }
}

function AgentNodeCard({
  data,
  selected,
  dimmed,
  onClick,
}: {
  data: { label: string; persona?: string; model?: string; state?: "done" | "running" | "pending" }
  selected: boolean
  dimmed?: boolean
  onClick: () => void
}) {
  const state = data.state ?? "pending"
  const stateRing =
    state === "running"
      ? "border-amber-400 ring-2 ring-amber-400/30"
      : state === "done"
        ? "border-emerald-500/60"
        : ""
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative h-full w-full rounded-md border bg-card px-3 py-2 text-left shadow-sm transition-colors",
        selected
          ? "border-primary ring-2 ring-primary/30"
          : "border-border hover:border-primary/50",
        dimmed ? "opacity-60" : "",
        stateRing
      )}
    >
      {state === "running" ? (
        <span className="absolute right-1.5 top-1.5 inline-block size-2 animate-pulse rounded-full bg-amber-400" />
      ) : null}
      <span className="block text-sm font-semibold">{data.label}</span>
      {data.persona ? (
        <span className="mt-0.5 block truncate text-xs text-muted-foreground">{data.persona}</span>
      ) : null}
      {data.model ? (
        <span className="mt-1 block truncate text-[10px] text-muted-foreground/70">
          model · {data.model}
        </span>
      ) : null}
    </button>
  )
}

function TermNode({ data }: NodeProps) {
  return (
    <div className="relative flex h-full w-full items-center justify-center">
      <Handle type="target" position={Position.Left} className={HANDLE_CLS} />
      <div className="flex h-full w-full items-center justify-center rounded-full border bg-muted px-4 py-1.5 text-xs font-semibold uppercase tracking-wider">
        {String(data?.label ?? "")}
      </div>
      <Handle type="source" position={Position.Right} className={HANDLE_CLS} />
    </div>
  )
}

function GroupNode({ data }: NodeProps) {
  return (
    <div className="relative flex h-full w-full items-center justify-center">
      <Handle type="target" position={Position.Left} className={HANDLE_CLS} />
      <div className="flex h-full w-full flex-col items-center justify-center rounded-md border-2 border-dashed border-primary/40 bg-primary/5 px-4 py-2 text-center text-sm font-semibold transition-colors hover:border-primary">
        {String(data?.label ?? "")}
        <span className="mt-0.5 text-[10px] font-normal text-muted-foreground">expand →</span>
      </div>
      <Handle type="source" position={Position.Right} className={HANDLE_CLS} />
    </div>
  )
}

function AgentNode({ data, selected }: NodeProps) {
  return (
    <div className="relative h-full w-full">
      <Handle type="target" position={Position.Left} className={HANDLE_CLS} />
      <AgentNodeCard
        data={data as FlowNodeData}
        selected={Boolean(selected)}
        onClick={() => {
          /* selection handled via onNodeClick on the canvas */
        }}
      />
      <Handle type="source" position={Position.Right} className={HANDLE_CLS} />
    </div>
  )
}

const nodeTypes = {
  agent: AgentNode,
  group: GroupNode,
  term: TermNode,
}

// Monaco is huge — only loaded when the prompt editor mounts.
const LazyPromptEditor = lazy(() =>
  import("@monaco-editor/react").then((m) => ({ default: m.default }))
)

export function AgentsPage() {
  const { data: spec, isLoading: specLoading } = useAgentGraph()
  const { data: agents, isLoading: agentsLoading, mutate: mutateAgents } = useAgents()
  const { resolved } = useTheme()
  const dark = resolved === "dark"

  // Live pipeline state — poll the newest task, then its progress.
  const { data: newest } = useSWR("/tasks?limit=1", () => listTasks(1), {
    refreshInterval: 3000,
  })
  const liveTaskId = newest?.[0]?.id
  const liveStatus = newest?.[0]?.status
  const live = liveStatus === "pending" || liveStatus === "running"
  const { data: liveProgress } = useSWR(
    liveTaskId && live ? `/tasks/${liveTaskId}/progress` : null,
    () => getTaskProgress(liveTaskId as string),
    { refreshInterval: live ? 3000 : 0 }
  )
  const { data: modelData } = useSWR("/models", () => listModels())
  const models: ModelInfo[] = modelData?.models ?? []

  const { nodes, edges } = useMemo(() => (spec ? buildGraph(spec) : { nodes: [], edges: [] }), [spec])
  const liveNodes = useMemo(
    () => applyLiveState(nodes, liveProgress),
    [nodes, liveProgress]
  )

  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [showSubflow, setShowSubflow] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<PromptPreview | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [loadingPreview, setLoadingPreview] = useState(false)

  const selected = agents?.find((a) => a.name === selectedName) ?? null
  const [draft, setDraft] = useState<AgentConfig | null>(null)

  function selectAgent(name: string | null) {
    setSelectedName(name)
    setError(null)
    const cfg = agents?.find((a) => a.name === name)
    setDraft(cfg ? { ...cfg } : null)
  }

  if (specLoading || agentsLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-[60vh] rounded-md" />
        <Skeleton className="h-40 rounded-md" />
      </div>
    )
  }

  if (!spec || !agents) {
    return <div className="text-sm text-muted-foreground">Failed to load agent graph.</div>
  }

  const subflowNodes: FlowNode[] = spec.subflow.nodes.map((n) => ({
    id: n.id,
    type: n.kind === "agent" ? "agent" : "term",
    position: { x: 0, y: 0 },
    data: { label: n.label, kind: n.kind, persona: n.persona, model: n.model },
  }))
  const subflowEdges: Edge[] = spec.subflow.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
    style: { strokeWidth: 2.5 },
  }))
  const layoutedSubflow = layoutNodes(subflowNodes, subflowEdges)

  const minimapColors = {
    backgroundColor: dark ? "#18181b" : "#ffffff",
    maskColor: dark ? "rgba(24,24,27,0.55)" : "rgba(255,255,255,0.6)",
    nodeColor: (n: { type?: string }) =>
      n.type === "agent" ? (dark ? "#7aa2ff" : "#2563eb") : dark ? "#71717a" : "#cbd5e1",
  }

  async function handleSave() {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const updated = await updateAgent(draft.name, {
        persona: draft.persona,
        role: draft.role,
        system_prompt: draft.system_prompt,
        model: draft.model,
        fallback_models: draft.fallback_models,
        temperature: draft.temperature,
        max_tokens: draft.max_tokens,
        is_active: draft.is_active,
      })
      await mutateAgents()
      setDraft({ ...updated })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const reset = await resetAgent(draft.name)
      await mutateAgents()
      setDraft({ ...reset })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed")
    } finally {
      setSaving(false)
    }
  }

  async function handlePreview() {
    if (!draft) return
    setLoadingPreview(true)
    try {
      const p = await promptPreview(draft.name)
      setPreview(p)
      setPreviewOpen(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed")
    } finally {
      setLoadingPreview(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
      <div className="space-y-4">
        <LiveRunCard
          taskId={liveTaskId}
          status={liveStatus}
          progress={liveProgress}
        />
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Pipeline graph</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[380px] overflow-hidden rounded-md border">
              <ReactFlow
                key={`pipeline-${nodes.length}`}
                nodes={liveNodes}
                edges={edges}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.25 }}
                onNodeClick={(_, node) => {
                  const agentName = spec.nodes.find((n) => n.id === node.id)?.agent
                  if (node.id === "process_all_formats") {
                    setShowSubflow((v) => !v)
                  } else if (agentName) {
                    selectAgent(agentName)
                  }
                }}
              >
                <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
                <Controls />
                <MiniMap
                  pannable
                  zoomable
                  position="bottom-left"
                  style={{ width: 130, height: 96 }}
                  bgColor={minimapColors.backgroundColor}
                  maskColor={minimapColors.maskColor}
                  nodeColor={minimapColors.nodeColor}
                />
              </ReactFlow>
            </div>
          </CardContent>
        </Card>

        {showSubflow && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{spec.subflow.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[260px] overflow-hidden rounded-md border">
                <ReactFlow
                  key={`subflow-${layoutedSubflow.length}`}
                  nodes={layoutedSubflow}
                  edges={subflowEdges}
                  nodeTypes={nodeTypes}
                  fitView
                  fitViewOptions={{ padding: 0.25 }}
                  onNodeClick={(_, node) => {
                    const agentName = spec.subflow.nodes.find((n) => n.id === node.id)?.agent
                    if (agentName) selectAgent(agentName)
                  }}
                >
                  <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
                  <Controls />
                </ReactFlow>
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Support agents</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {spec.aux_lanes.map((lane) => (
              <div key={lane.id}>
                <p className="mb-2 text-xs font-medium text-muted-foreground">{lane.label}</p>
                <div className="flex flex-wrap items-center gap-2">
                  {lane.agents.map((a, i) => (
                    <div key={a.name} className="flex items-center gap-2">
                      {i > 0 ? <ArrowRight className="size-4 shrink-0 text-muted-foreground/50" /> : null}
                      <div className="w-48">
                        <AgentNodeCard
                          data={{ label: a.name, persona: a.persona, model: a.model }}
                          selected={selectedName === a.name}
                          dimmed={!a.is_active}
                          onClick={() => selectAgent(a.name)}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <aside className="space-y-4 self-start">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Agent config</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {draft ? (
              <>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-semibold">{draft.persona || draft.name}</span>
                    <Badge variant={draft.source === "seed" ? "secondary" : "outline"}>{draft.source}</Badge>
                  </div>
                  <Badge variant={draft.is_active ? "default" : "destructive"}>
                    {draft.is_active ? "active" : "inactive"}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="persona">Persona</Label>
                    <Input id="persona" value={draft.persona} onChange={(e) => setDraft({ ...draft, persona: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="model">Model</Label>
                    <Select value={draft.model} onValueChange={(v) => setDraft({ ...draft, model: v })}>
                      <SelectTrigger id="model" className="w-full min-w-0">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="max-w-[var(--radix-select-trigger-width)]">
                        {models.map((m) => (
                          <SelectItem key={m.id} value={m.id}>
                            <span className="min-w-0 flex-1 truncate">{m.name}</span>
                            <span className="shrink-0 text-xs text-muted-foreground">
                              {m.rpd} RPD
                            </span>
                          </SelectItem>
                        ))}
                        {!models.some((m) => m.id === draft.model) && draft.model ? (
                          <SelectItem value={draft.model}>{draft.model}</SelectItem>
                        ) : null}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="fallback">Fallback models (comma-separated)</Label>
                  <Input
                    id="fallback"
                    placeholder="gemini-3.1-flash-lite, gemini-3.5-flash-lite"
                    value={(draft.fallback_models ?? []).join(", ")}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        fallback_models: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                      })
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="role">Role</Label>
                  <Input id="role" value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })} />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="temperature">Temperature</Label>
                    <Input
                      id="temperature"
                      type="number"
                      step={0.05}
                      min={0}
                      max={2}
                      value={draft.temperature}
                      onChange={(e) => setDraft({ ...draft, temperature: Number(e.target.value) })}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="maxTokens">Max tokens</Label>
                    <Input
                      id="maxTokens"
                      type="number"
                      step={64}
                      min={64}
                      value={draft.max_tokens}
                      onChange={(e) => setDraft({ ...draft, max_tokens: Number(e.target.value) })}
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="system_prompt">System prompt</Label>
                  <div className="h-56 overflow-hidden rounded-md border">
                    <Suspense fallback={<Skeleton className="h-full w-full" />}>
                      <LazyPromptEditor
                        language="markdown"
                        value={draft.system_prompt}
                        onChange={(v) => setDraft({ ...draft, system_prompt: v ?? "" })}
                        options={{ minimap: { enabled: false }, fontSize: 12, wordWrap: "on", scrollBeyondLastLine: false, tabSize: 2 }}
                      />
                    </Suspense>
                  </div>
                </div>

                {error ? <p className="text-sm text-destructive">{error}</p> : null}

                <div className="flex flex-wrap items-center gap-2">
                  <Button onClick={handleSave} disabled={saving || !selected}>
                    {saving ? "Saving…" : "Save"}
                  </Button>
                  <Button variant="outline" onClick={handleReset} disabled={saving}>
                    Reset to seed
                  </Button>
                  <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline" onClick={handlePreview} disabled={loadingPreview || !selected}>
                        {loadingPreview ? "Loading…" : "Preview prompt"}
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-3xl">
                      <DialogHeader>
                        <DialogTitle>Prompt preview — {draft.name}</DialogTitle>
                      </DialogHeader>
                      <div className="grid gap-4">
                        {preview ? (
                          <>
                            <PromptBlock title="System prompt (DB)" text={preview.system_prompt} />
                            <PromptBlock title="User prompt (assembled at run time)" text={preview.user_prompt} />
                          </>
                        ) : (
                          <p className="text-sm text-muted-foreground">Assembling…</p>
                        )}
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Click an agent node on the graph to edit its prompt, model, and parameters.
              </p>
            )}
          </CardContent>
        </Card>
      </aside>
    </div>
  )
}

function PromptBlock({ title, text }: { title: string; text: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted-foreground">{title}</p>
      <ScrollArea className="h-64 rounded-md border bg-muted/30">
        <pre className="whitespace-pre-wrap break-words p-3 font-mono text-xs leading-relaxed">
          {text}
        </pre>
      </ScrollArea>
    </div>
  )
}

// ─── Live pipeline overlay ─────────────────────────────────────────────────

/** Map a pipeline node id to its runtime state from the progress %.
 *
 * Progress lands at 10 (strategist) → 25 (copywriter) → 50+ (per-format
 * chain) → 100 (done). A node is "done" once a later threshold is reached.
 */
function nodeStateFor(id: string, pct: number): "done" | "running" | "pending" {
  switch (id) {
    case "strategist":
      return pct >= 25 ? "done" : pct >= 10 ? "running" : "pending"
    case "copywriter":
      return pct >= 50 ? "done" : pct >= 25 ? "running" : "pending"
    case "process_all_formats":
      return pct >= 100 ? "done" : pct >= 50 ? "running" : "pending"
    default:
      return "pending"
  }
}

function applyLiveState(
  nodes: FlowNode[],
  progress: TaskProgress | undefined
): FlowNode[] {
  if (!progress) return nodes
  return nodes.map((n) => ({
    ...n,
    data: { ...n.data, state: nodeStateFor(n.id, progress.pct) },
  }))
}

function LiveRunCard({
  taskId,
  status,
  progress,
}: {
  taskId?: string
  status?: string
  progress?: TaskProgress
}) {
  const live = status === "pending" || status === "running"
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-sm">
          <Activity className="size-3.5" />
          Pipeline status
          {live ? (
            <span className="inline-block size-2 animate-pulse rounded-full bg-amber-400" />
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        {!taskId ? (
          <p className="text-muted-foreground">No tasks yet — run a generation to watch the agents live.</p>
        ) : (
          <>
            <p className="font-mono text-muted-foreground">
              {taskId} · <span className="text-foreground">{status}</span>
            </p>
            {progress ? (
              <>
                <p>
                  {progress.pct}% — {progress.node}
                  {progress.total > 0 ? ` · ${progress.done}/${progress.total} formats verified` : ""}
                </p>
                {progress.total > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(progress.per_format).map(([fmt, v]) => (
                      <span
                        key={fmt}
                        className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5"
                      >
                        <span
                          className={cn(
                            "inline-block size-2 rounded-full",
                            v.status === "verified" ? "bg-emerald-500" : "bg-amber-400 animate-pulse"
                          )}
                        />
                        {fmt} · {v.status}
                      </span>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <p className="text-muted-foreground">Waiting for the pipeline to report…</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
