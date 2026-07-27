<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";

  onMount(() => {
    goto("/configure?tab=brand", { replaceState: true });
  });
</script>
