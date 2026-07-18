<script lang="ts">
  import "../app.css";
  import { page } from "$app/stores";

  let { children } = $props();

  const links = [
    { href: "/", label: "Dashboard" },
    { href: "/generate", label: "Generate" },
    { href: "/templates", label: "Templates" },
    { href: "/tokens", label: "Tokens" },
    { href: "/tasks", label: "Tasks" },
    { href: "/settings", label: "Settings" },
  ];

  function isActive(href: string) {
    if (href === "/") return $page.url.pathname === "/";
    return $page.url.pathname.startsWith(href);
  }
</script>

<div class="min-h-screen bg-black text-white flex" style="font-family: var(--font-body)">
  <aside class="w-48 shrink-0 bg-[#080808] border-r border-[#1c1c1c] flex flex-col">
    <div class="h-12 flex items-center px-5 border-b border-[#1c1c1c]">
      <span class="text-sm font-medium tracking-tight text-white">tasbir</span>
    </div>
    <nav class="flex-1 py-3">
      {#each links as link}
        <a
          href={link.href}
          class="relative flex items-center h-9 px-5 text-sm transition-colors {isActive(link.href) ? 'text-white' : 'text-gray-600 hover:text-gray-400'}"
        >
          {#if isActive(link.href)}
            <span class="absolute left-0 top-1 bottom-1 w-[2px] bg-white rounded-r" />
          {/if}
          {link.label}
        </a>
      {/each}
    </nav>
    <div class="px-5 py-3 border-t border-[#1c1c1c]">
      <span class="text-xs text-gray-600">tasbir v0.2</span>
    </div>
  </aside>
  <main class="flex-1 min-w-0">
    {@render children()}
  </main>
</div>
