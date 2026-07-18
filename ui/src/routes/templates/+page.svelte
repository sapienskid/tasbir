<script lang="ts">
  import { onMount } from "svelte";
  import Button from "$lib/components/ui/button.svelte";
  import { listTemplates, createTemplate, updateTemplate, deleteTemplate, type Template } from "$lib/api/templates";

  let templates = $state<Template[]>([]);
  let loading = $state(true);
  let error = $state("");

  let editing: Template | null = $state(null);
  let editName = $state("");
  let editHtml = $state("");
  let editDesc = $state("");
  let saving = $state(false);

  onMount(async () => {
    try { templates = await listTemplates(false); }
    catch (e) { error = "Failed to load templates"; }
    finally { loading = false; }
  });

  function startNew() {
    editing = { id: "", name: "", description: "", html: "", slots: {}, enabled: true };
    editName = "";
    editHtml = "";
    editDesc = "";
  }

  function startEdit(t: Template) {
    editing = t;
    editName = t.name;
    editHtml = t.html;
    editDesc = t.description;
  }

  function cancelEdit() {
    editing = null;
    editName = "";
    editHtml = "";
    editDesc = "";
  }

  async function handleSave() {
    if (!editName.trim() || !editHtml.trim()) return;
    saving = true;
    error = "";
    try {
      if (editing && editing.id) {
        const updated = await updateTemplate(editing.id, { name: editName, html: editHtml, description: editDesc });
        templates = templates.map((t) => (t.id === editing!.id ? updated : t));
      } else {
        const created = await createTemplate({ name: editName, html: editHtml, description: editDesc });
        templates = [created, ...templates];
      }
      cancelEdit();
    } catch (e) {
      error = e instanceof Error ? e.message : "Save failed";
    } finally { saving = false; }
  }

  async function handleDelete(id: string) {
    try {
      await deleteTemplate(id);
      templates = templates.filter((t) => t.id !== id);
    } catch {}
  }

  async function handleToggle(t: Template) {
    try {
      const updated = await updateTemplate(t.id, { enabled: !t.enabled });
      templates = templates.map((x) => (x.id === t.id ? updated : x));
    } catch {}
  }
</script>

<div class="p-8 max-w-2xl">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-lg font-medium text-white">Templates</h1>
    {#if !editing}
      <Button variant="secondary" size="sm" onclick={startNew}>New</Button>
    {/if}
  </div>

  {#if error}
    <p class="text-xs text-gray-600 mb-4">{error}</p>
  {/if}

  {#if editing}
    <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-4 mb-6 space-y-3">
      <input
        bind:value={editName}
        class="w-full h-9 bg-black text-white text-sm rounded-lg border border-[#1c1c1c] px-3 focus:border-[#333] focus:outline-none"
        placeholder="Template name"
      />
      <input
        bind:value={editDesc}
        class="w-full h-9 bg-black text-white text-sm rounded-lg border border-[#1c1c1c] px-3 focus:border-[#333] focus:outline-none"
        placeholder="Description (optional)"
      />
      <p class="text-xs text-gray-600">HTML</p>
      <textarea
        bind:value={editHtml}
        rows={8}
        class="w-full bg-black text-white text-xs rounded-lg border border-[#1c1c1c] px-3 py-2 font-mono leading-relaxed focus:border-[#333] focus:outline-none resize-y"
        placeholder="<div>...</div>"
      ></textarea>
      <div class="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onclick={cancelEdit}>Cancel</Button>
        <Button variant="primary" size="sm" disabled={saving || !editName.trim() || !editHtml.trim()} onclick={handleSave}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  {/if}

  {#if loading}
    <p class="text-sm text-gray-600">Loading…</p>
  {:else if templates.length === 0 && !editing}
    <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] p-8 text-center">
      <p class="text-sm text-gray-600">No templates yet.</p>
    </div>
  {:else if !editing}
    <div class="space-y-1.5">
      {#each templates as tmpl}
        <div class="rounded-lg border border-[#1c1c1c] bg-[#080808] px-4 py-3 transition-colors hover:border-[#333]">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-sm text-white truncate">{tmpl.name}</span>
              <button class="text-xs text-gray-600 hover:text-gray-400 transition-colors" onclick={() => handleToggle(tmpl)}>
                {tmpl.enabled ? "enabled" : "disabled"}
              </button>
            </div>
            <div class="flex gap-1 shrink-0">
              <Button variant="ghost" size="sm" onclick={() => startEdit(tmpl)}>edit</Button>
              <Button variant="ghost" size="sm" onclick={() => handleDelete(tmpl.id)}>delete</Button>
            </div>
          </div>
          {#if tmpl.description}
            <p class="text-xs text-gray-600 mt-1 truncate">{tmpl.description}</p>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
