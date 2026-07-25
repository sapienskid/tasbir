<script lang="ts">
  import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "$lib/components/ui/dialog/index.js";
  import { Button } from "$lib/components/ui/button/index.js";

  let {
    open = false,
    title = "Confirm",
    message = "",
    confirmLabel = "Delete",
    variant = "destructive" as "destructive" | "default" | "outline",
    loading = false,
    onconfirm,
    oncancel,
  } = $props();
</script>

<Dialog bind:open>
  <DialogContent class="sm:max-w-sm">
    <DialogHeader>
      <DialogTitle>{title}</DialogTitle>
      <DialogDescription>{message}</DialogDescription>
    </DialogHeader>
    <div class="flex justify-end gap-2">
      <Button variant="outline" size="sm" onclick={oncancel}>Cancel</Button>
      <Button
        variant={variant}
        size="sm"
        disabled={loading}
        onclick={onconfirm}
      >
        {loading ? "..." : confirmLabel}
      </Button>
    </div>
  </DialogContent>
</Dialog>
