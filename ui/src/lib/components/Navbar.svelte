<script lang="ts">
  import { page } from "$app/stores";

  const links = [
    { href: "/", label: "Home" },
    { href: "/generate", label: "Generate" },
    { href: "/templates", label: "Templates" },
    { href: "/tokens", label: "Tokens" },
    { href: "/settings", label: "Settings" },
  ];
</script>

<nav class="bg-white border-b border-gray-200 px-6 py-3">
  <div class="max-w-7xl mx-auto flex items-center justify-between">
    <a href="/" class="text-xl font-bold text-indigo-600">Tasbir</a>
    <div class="flex gap-6 text-sm font-medium">
      {#each links as link}
        <a
          href={link.href}
          class="transition-colors {$page.url.pathname === link.href ? 'text-indigo-600' : 'text-gray-600 hover:text-gray-900'}"
        >
          {link.label}
        </a>
      {/each}
    </div>
  </div>
</nav>
