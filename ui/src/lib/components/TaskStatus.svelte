<script lang="ts">
  import { cn } from "$lib/utils";

  let {
    status = "pending",
    progress = 0,
    error = "",
  }: { status?: string; progress?: number; error?: string } = $props();

  const statusColors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    running: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };

  const statusLabels: Record<string, string> = {
    pending: "Pending",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
  };
</script>

<div class="space-y-2">
  <div class="flex items-center gap-2">
    <span class={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", statusColors[status] || "")}>
      {statusLabels[status] || status}
    </span>
    {#if status === "running"}
      <span class="text-sm text-gray-500">{progress}%</span>
    {/if}
  </div>

  {#if status === "running"}
    <div class="w-full bg-gray-200 rounded-full h-2">
      <div class="bg-indigo-600 rounded-full h-2 transition-all" style="width: {progress}%"></div>
    </div>
  {/if}

  {#if error}
    <p class="text-sm text-red-600">{error}</p>
  {/if}
</div>
