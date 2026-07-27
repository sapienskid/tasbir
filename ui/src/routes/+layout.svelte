<script lang="ts">
  import "../app.css";
  import { page } from "$app/stores";
  import { fly } from "svelte/transition";
  import {
    LayoutDashboard, Sparkles, Image, FileCode, Cog, Bug, Menu, X
  } from "lucide-svelte";

  let { children } = $props();

  let sidebarOpen = $state(false);

  const links = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/create", label: "Create", icon: Sparkles },
    { href: "/assets", label: "Assets", icon: Image },
    { href: "/templates", label: "Templates", icon: FileCode },
    { href: "/configure", label: "Configure", icon: Cog },
  ];

  function isActive(href: string) {
    if (href === "/") return $page.url.pathname === "/";
    return $page.url.pathname.startsWith(href);
  }
</script>

<div class="min-h-screen bg-bg text-text flex">
  <!-- Mobile overlay -->
  {#if sidebarOpen}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div
      class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
      onclick={() => sidebarOpen = false}
      onkeydown={(e) => e.key === 'Escape' && (sidebarOpen = false)}
      role="button"
      tabindex="-1"
      transition:fly={{ duration: 200, opacity: 0 }}
    ></div>
  {/if}

  <!-- Sidebar -->
  <aside
    class="fixed lg:sticky top-0 left-0 z-50 h-screen w-56 bg-surface border-r border-border flex flex-col transition-transform duration-200 {sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0"
  >
    <div class="h-14 flex items-center gap-2.5 px-5 border-b border-border">
          <div class="w-2 h-2 rounded-full bg-accent"></div>
      <span class="text-sm font-medium tracking-tight text-text" style="font-family: var(--font-display)">tasbir</span>
      <button
        class="ml-auto lg:hidden text-text-secondary hover:text-text transition-colors"
        onclick={() => sidebarOpen = false}
      >
        <X size={16} />
      </button>
    </div>

    <nav class="flex-1 py-4 space-y-1 px-2">
      {#each links as link}
        <a
          href={link.href}
          class="flex items-center gap-3 h-9 px-3 text-sm rounded-lg transition-colors {isActive(link.href) ? 'bg-accent/10 text-accent' : 'text-text-secondary hover:bg-elevated hover:text-text'}"
          onclick={() => sidebarOpen = false}
        >
          <link.icon size={16} />
          {link.label}
        </a>
      {/each}
    </nav>

    <div class="px-5 py-4 border-t border-border">
      <span class="text-xs text-text-secondary">tasbir v0.2</span>
    </div>
  </aside>

  <!-- Main content -->
  <main class="flex-1 min-w-0">
    <!-- Mobile header -->
    <div class="sticky top-0 z-30 lg:hidden bg-bg/80 backdrop-blur border-b border-border">
      <div class="flex items-center h-14 px-4 gap-3">
        <button
          class="text-text-secondary hover:text-text transition-colors"
          onclick={() => sidebarOpen = true}
        >
          <Menu size={20} />
        </button>
        <div class="flex items-center gap-2">
      <div class="w-2 h-2 rounded-full bg-accent"></div>
          <span class="text-sm font-medium" style="font-family: var(--font-display)">tasbir</span>
        </div>
      </div>
    </div>
    <div class="p-6 sm:p-8">
      {@render children()}
    </div>
  </main>
</div>
