<script lang="ts">
  import { onMount } from "svelte";
  import Button from "$lib/components/ui/button.svelte";
  import { apiKey } from "$lib/stores/auth";
  import { getSettings } from "$lib/api/settings";
  import { api } from "$lib/api/client";

  let loading = $state(true);
  let saving = $state(false);
  let saveError = $state("");
  let saveSuccess = $state("");
  let keyInput = $state("");
  let fields = $state<Record<string, string>>({});

  const sections = [
    {
      id: "ghost",
      name: "Ghost CMS",
      desc: "Auto-generate assets when posts are published.",
      fields: [
        { key: "ghost_url", label: "Ghost URL" },
      ],
    },
    {
      id: "penpot",
      name: "Penpot",
      desc: "Sync design tokens from Penpot.",
      fields: [
        { key: "penpot_url", label: "Penpot URL" },
      ],
    },
    {
      id: "storage",
      name: "Storage",
      desc: "MinIO/S3-compatible storage for generated assets.",
      fields: [
        { key: "minio_endpoint", label: "MinIO Endpoint" },
        { key: "minio_bucket", label: "MinIO Bucket" },
      ],
    },
  ];

  onMount(async () => {
    keyInput = $apiKey;
    try {
      const res = await getSettings();
      const data = res.data as Record<string, string>;
      for (const section of sections) {
        for (const f of section.fields) {
          fields[f.key] = data[f.key] || "";
        }
      }
    } catch {} finally { loading = false; }
  });

  function saveKey() {
    apiKey.setKey(keyInput);
  }

  async function handleSave() {
    saving = true;
    saveError = "";
    saveSuccess = "";
    try {
      await api.put("/settings", { data: fields });
      saveSuccess = "Settings saved.";
      setTimeout(() => (saveSuccess = ""), 3000);
    } catch (e) {
      saveError = e instanceof Error ? e.message : "Save failed.";
    } finally { saving = false; }
  }
</script>

<div class="p-8 max-w-2xl">
  <h1 class="text-lg font-medium text-white mb-6">Settings</h1>

  {#if loading}
    <p class="text-sm text-gray-600">Loading…</p>
  {:else}
    <div class="space-y-4">
      <section class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-4">
        <h2 class="text-sm font-medium text-white mb-1">API Key</h2>
        <p class="text-xs text-gray-600 mb-3">Your key for authenticating with the Tasbir backend.</p>
        <div class="flex gap-2">
          <input
            bind:value={keyInput}
            class="flex-1 h-9 bg-black text-white text-xs rounded-lg border border-[#1c1c1c] px-3 focus:border-[#333] focus:outline-none font-mono"
            placeholder="sk-…"
          />
          <Button variant="primary" size="sm" onclick={saveKey}>Save</Button>
        </div>
      </section>

      {#each sections as section}
        {@const hasValue = section.fields.some((f) => fields[f.key]?.trim())}
        {#if hasValue}
          <section class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-4">
            <h2 class="text-sm font-medium text-white mb-1">{section.name}</h2>
            <p class="text-xs text-gray-600 mb-3">{section.desc}</p>
            <div class="space-y-2.5">
              {#each section.fields as fld}
                <div>
                  <label class="text-xs text-gray-600 block mb-1">{fld.label}</label>
                  <input bind:value={fields[fld.key]} class="w-full h-9 bg-black text-white text-xs rounded-lg border border-[#1c1c1c] px-3 focus:border-[#333] focus:outline-none" />
                </div>
              {/each}
            </div>
          </section>
        {/if}
      {/each}

      {#if saveError}
        <p class="text-xs text-gray-600">{saveError}</p>
      {/if}
      {#if saveSuccess}
        <p class="text-xs text-white">{saveSuccess}</p>
      {/if}

      <div class="flex justify-end pt-2">
        <Button variant="primary" disabled={saving} onclick={handleSave}>
          {saving ? "Saving…" : "Save settings"}
        </Button>
      </div>
    </div>
  {/if}
</div>
