<script lang="ts">
  import { onMount } from "svelte";
  import Confirm from "$lib/components/ui/confirm.svelte";
  import { Button } from "$lib/components/ui/button/index.js";
  import { Card } from "$lib/components/ui/card/index.js";
  import { api } from "$lib/api/client";

  let templates = $state<any[]>([]);
  let loading = $state(true);
  let error = $state("");

  let creating = $state(false);
  let editing = $state<string | null>(null);
  let formName = $state("");
  let formDescription = $state("");
  let formHtml = $state("");
  let saving = $state(false);
  let confirmDelete = $state<string | null>(null);

  onMount(async () => {
    try {
      templates = await api.get(`/templates?enabled_only=false`);
    } catch { error = "Failed to load templates"; }
    finally { loading = false; }
  });

  function startCreate() {
    creating = true;
    editing = null;
    formName = "";
    formDescription = "";
    formHtml = '<!DOCTYPE html>\n<html>\n<head>\n  <script src="https://cdn.tailwindcss.com"><\/script>\n</head>\n<body>\n  <div class="w-full h-full flex items-center justify-center bg-black text-white">\n    <h1 class="text-4xl font-bold">{{HEADLINE}}</h1>\n  </div>\n</body>\n</html>';
    error = "";
  }

  function startEdit(id: string) {
    const t = templates.find(t => t.id === id);
    if (!t) return;
    creating = false;
    editing = id;
    formName = t.name;
    formDescription = t.description;
    formHtml = t.html;
    error = "";
  }

  function cancelForm() {
    creating = false;
    editing = null;
  }

  async function saveTemplate() {
    if (!formName.trim() || !formHtml.trim()) return;
    saving = true;
    error = "";
    try {
      if (editing) {
        await api.put(`/templates/${editing}`, { name: formName, description: formDescription, html: formHtml });
      } else {
        await api.post("/templates", { name: formName, description: formDescription, html: formHtml, slots: {} });
      }
      templates = await api.get("/templates?enabled_only=false");
      cancelForm();
    } catch (e) {
      error = e instanceof Error ? e.message : "Save failed";
    } finally { saving = false; }
  }

  async function deleteTemplate(id: string) {
    try {
      await api.delete(`/templates/${id}`);
      templates = templates.filter(t => t.id !== id);
    } catch { /* ignore */ }
  }
</script>

<div class="max-w-6xl space-y-6">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-lg font-medium text-text" style="font-family: var(--font-display)">Templates</h1>
      <p class="text-sm text-text-secondary mt-0.5">HTML templates the designer agent can use as starting points for asset generation.</p>
    </div>
    <Button variant="default" size="sm" onclick={startCreate}>New template</Button>
  </div>

  {#if creating || editing}
    <Card class="p-5">
      <h2 class="text-sm font-medium text-text mb-4">{editing ? "Edit template" : "New template"}</h2>
      <div class="space-y-4">
        <div>
          <label class="text-xs text-text-secondary block mb-1">Name</label>
          <input bind:value={formName} class="w-full h-9 bg-bg text-text text-sm rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none" placeholder="Dark minimalist" />
        </div>
        <div>
          <label class="text-xs text-text-secondary block mb-1">Description</label>
          <input bind:value={formDescription} class="w-full h-9 bg-bg text-text text-sm rounded-xl border border-border px-3 focus:border-border-focus focus:outline-none" placeholder="A dark, minimal template for Instagram" />
        </div>
        <div>
          <label class="text-xs text-text-secondary block mb-1">HTML (use <code class="text-text-secondary">&#123;&#123;HEADLINE&#125;&#125;</code>, <code class="text-text-secondary">&#123;&#123;BODY&#125;&#125;</code>, <code class="text-text-secondary">&#123;&#123;CTA&#125;&#125;</code> as placeholders)</label>
          <textarea bind:value={formHtml} rows={10} class="w-full bg-bg text-text text-xs leading-relaxed rounded-xl border border-border px-3 py-2 focus:border-border-focus focus:outline-none resize-none font-mono"></textarea>
        </div>
        {#if formHtml}
          <div>
            <p class="text-xs text-text-secondary block mb-1.5">Preview</p>
            <div class="rounded-xl border border-border overflow-hidden" style="width:360px;height:360px;">
              <iframe title="Template preview" srcdoc={formHtml.replace(/\{\{HEADLINE\}\}/g, "Headline").replace(/\{\{BODY\}\}/g, "Body text here").replace(/\{\{CTA\}\}/g, "Learn more")} class="w-full h-full border-0"></iframe>
            </div>
          </div>
        {/if}
        {#if error}
          <p class="text-xs text-destructive">{error}</p>
        {/if}
        <div class="flex gap-2">
          <Button variant="default" size="sm" disabled={saving} onclick={saveTemplate}>{saving ? "Saving…" : "Save"}</Button>
          <Button variant="ghost" size="sm" onclick={cancelForm}>Cancel</Button>
        </div>
      </div>
    </Card>
  {/if}

  {#if loading}
    <p class="text-sm text-text-secondary">Loading…</p>
  {:else if templates.length === 0 && !creating}
    <Card class="p-8 text-center">
      <p class="text-sm text-text-secondary">No templates yet. Create one to give the designer agent a starting point.</p>
    </Card>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each templates as t}
        <Card class="overflow-hidden hover:border-border-focus transition-colors">
          <div class="aspect-[4/3] bg-bg overflow-hidden">
            {#if t.html}
              <iframe title={t.name} srcdoc={t.html.replace(/\{\{HEADLINE\}\}/g, "Headline").replace(/\{\{BODY\}\}/g, "Body text").replace(/\{\{CTA\}\}/g, "CTA")} class="w-full h-full border-0" loading="lazy" style="pointer-events:none"></iframe>
            {/if}
          </div>
          <div class="p-4">
            <div class="flex items-center justify-between mb-1">
              <h3 class="text-sm text-text font-medium">{t.name}</h3>
              <span class="text-[10px] text-text-secondary">{t.enabled ? "active" : "disabled"}</span>
            </div>
            {#if t.description}
              <p class="text-xs text-text-secondary mb-3">{t.description}</p>
            {/if}
            <div class="flex gap-2">
              <button onclick={() => startEdit(t.id)} class="text-xs text-text-secondary hover:text-text transition-colors">Edit</button>
              <button onclick={() => confirmDelete = t.id} class="text-xs text-text-secondary hover:text-destructive transition-colors">Delete</button>
            </div>
          </div>
        </Card>
      {/each}
    </div>
  {/if}
</div>

<Confirm
  open={confirmDelete !== null}
  title="Delete template"
  message="Delete this template? This cannot be undone."
  confirmLabel="Delete"
  variant="destructive"
  onconfirm={() => { const id = confirmDelete; confirmDelete = null; if (id) deleteTemplate(id); }}
  oncancel={() => confirmDelete = null}
/>
