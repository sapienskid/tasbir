<script lang="ts">
  import { Card } from "$lib/components/ui/card/index.js";

  const WEBHOOK_URL = "http://localhost:8000/api/webhooks/ghost";
</script>

<div class="max-w-3xl space-y-6">
  <div>
    <a href="/configure" class="inline-flex items-center text-xs text-text-secondary hover:text-text transition-colors">&larr; Configure</a>
    <h1 class="text-lg font-medium text-text mt-3" style="font-family: var(--font-display)">Ghost Webhook Setup</h1>
    <p class="text-sm text-text-secondary mt-0.5">Configure Ghost CMS to send a webhook when a post is published, triggering automatic asset generation.</p>
  </div>

  <Card class="p-6">
    <h2 class="text-sm font-medium text-text mb-3">Webhook URL</h2>
    <p class="text-xs text-text-secondary mb-2">Add this URL as a webhook in your Ghost Admin panel.</p>
    <div class="bg-bg rounded-xl border border-border px-4 py-3 font-mono text-xs text-accent break-all select-all">
      {WEBHOOK_URL}
    </div>
  </Card>

  <Card class="p-6">
    <h2 class="text-sm font-medium text-text mb-3">Step-by-step guide</h2>
    <ol class="space-y-3 text-sm text-text-secondary">
      <li class="flex gap-3">
        <span class="text-accent font-mono shrink-0">1.</span>
          <span>Log in to your Ghost Admin panel at <code class="text-text font-mono text-xs">{"{"}your-ghost-url{"}"}/ghost</code>.</span>
      </li>
      <li class="flex gap-3">
        <span class="text-accent font-mono shrink-0">2.</span>
        <span>Navigate to <strong class="text-text">Settings &rarr; Integrations</strong>.</span>
      </li>
      <li class="flex gap-3">
        <span class="text-accent font-mono shrink-0">3.</span>
        <span>Click <strong class="text-text">Add custom integration</strong>. Name it "Tasbir" or anything recognizable.</span>
      </li>
      <li class="flex gap-3">
        <span class="text-accent font-mono shrink-0">4.</span>
        <div class="space-y-1">
          <span>Copy the <strong class="text-text">Admin API Key</strong> (format: <code class="text-text font-mono text-xs">id:secret</code>) — you'll need this for the environment variable <code class="text-text font-mono text-xs">GHOST_ADMIN_API_KEY</code>.</span>
        </div>
      </li>
      <li class="flex gap-3">
        <span class="text-accent font-mono shrink-0">5.</span>
        <div class="space-y-1">
          <span>Generate a <strong class="text-text">webhook secret</strong> (a random string) and set it as <code class="text-text font-mono text-xs">GHOST_WEBHOOK_SECRET</code> in your <code class="text-text font-mono text-xs">.env</code> file.</span>
        </div>
      </li>
      <li class="flex gap-3">
        <span class="text-accent font-mono shrink-0">6.</span>
        <div class="space-y-1">
          <span>In the integration settings, add a new webhook:</span>
          <div class="bg-bg rounded-xl border border-border p-3 text-xs space-y-1 mt-2">
            <p><span class="text-text">Event:</span> <span class="font-mono">Post published</span></p>
            <p><span class="text-text">URL:</span> <span class="font-mono text-accent">{WEBHOOK_URL}</span></p>
            <p><span class="text-text">Secret:</span> <span class="font-mono">The secret you generated in step 5</span></p>
          </div>
        </div>
      </li>
      <li class="flex gap-3">
        <span class="text-accent font-mono shrink-0">7.</span>
        <span>Save the webhook. Tasbir will now automatically generate assets when a post is published.</span>
      </li>
    </ol>
  </Card>

  <Card class="p-6">
    <h2 class="text-sm font-medium text-text mb-3">Required environment variables</h2>
    <p class="text-xs text-text-secondary mb-3">Add these to your <code class="text-text font-mono text-xs">.env</code> file:</p>
    <div class="space-y-2">
      <div class="bg-bg rounded-xl border border-border px-4 py-3">
        <p class="text-xs text-text font-mono">GHOST_URL=<span class="text-text-secondary">https://your-ghost-instance.com</span></p>
        <p class="text-xs text-text-secondary mt-0.5">Your Ghost CMS URL.</p>
      </div>
      <div class="bg-bg rounded-xl border border-border px-4 py-3">
        <p class="text-xs text-text font-mono">GHOST_ADMIN_API_KEY=<span class="text-text-secondary">id:secret</span></p>
        <p class="text-xs text-text-secondary mt-0.5">Admin API key from step 4.</p>
      </div>
      <div class="bg-bg rounded-xl border border-border px-4 py-3">
        <p class="text-xs text-text font-mono">GHOST_WEBHOOK_SECRET=<span class="text-text-secondary">your-secret</span></p>
        <p class="text-xs text-text-secondary mt-0.5">Webhook secret from step 5.</p>
      </div>
    </div>
  </Card>

  <Card class="p-6">
    <h2 class="text-sm font-medium text-text mb-3">Troubleshooting</h2>
    <div class="space-y-3 text-xs text-text-secondary">
      <p><strong class="text-text">Webhook not firing?</strong> Check that your Ghost instance can reach the Tasbir server. If they're on different networks, the webhook URL needs to be publicly accessible.</p>
      <p><strong class="text-text">Invalid signature errors?</strong> Make sure the webhook secret in Ghost Admin matches <code class="text-text font-mono text-xs">GHOST_WEBHOOK_SECRET</code> exactly.</p>
      <p><strong class="text-text">Assets not generated?</strong> Verify the <code class="text-text font-mono text-xs">GEMINI_API_KEY</code> is set and the pipeline completes successfully via the Create page.</p>
    </div>
  </Card>
</div>
