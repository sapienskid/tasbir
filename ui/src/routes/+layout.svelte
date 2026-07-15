<script lang="ts">
  import "../app.css";
  let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50">
  <nav class="bg-white border-b border-gray-200 px-6 py-3">
    <div class="max-w-7xl mx-auto flex items-center justify-between">
      <a href="/" class="text-xl font-bold text-gray-900">Tasbir</a>
      <div class="flex gap-6 text-sm font-medium text-gray-600">
        <a href="/generate" class="hover:text-gray-900">Generate</a>
        <a href="/templates" class="hover:text-gray-900">Templates</a>
        <a href="/tokens" class="hover:text-gray-900">Tokens</a>
        <a href="/settings" class="hover:text-gray-900">Settings</a>
      </div>
    </div>
  </nav>
  <main class="max-w-7xl mx-auto px-6 py-8">
    {#render children()}
  </main>
</div>
