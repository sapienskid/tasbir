<script lang="ts">
  let { data, tokenId }: { data: Record<string, unknown>; tokenId: string } = $props();

  let activeFont = $state("");

  function resolveRef(ref: string, d: Record<string, unknown>): string {
    const path = ref.replace(/[{}]/g, "").split(".");
    let val: unknown = d;
    for (const key of path) {
      if (val && typeof val === "object" && key in (val as Record<string, unknown>)) {
        val = (val as Record<string, unknown>)[key];
      } else return ref;
    }
    if (val && typeof val === "object" && ("value" in (val as Record<string, unknown>) || "$value" in (val as Record<string, unknown>))) {
      return resolveRef(String((val as Record<string, unknown>).value || (val as Record<string, unknown>).$value), d);
    }
    return String(val);
  }

  function collectCategories(d: Record<string, unknown>): string[] {
    return Object.keys(d).filter(k => d[k] && typeof d[k] === "object");
  }

  function collectLeaves(obj: Record<string, unknown>, d: Record<string, unknown>): { name: string; resolved: string }[] {
    const result: { name: string; resolved: string }[] = [];
    for (const [k, v] of Object.entries(obj)) {
      if (v && typeof v === "object" && ("value" in (v as Record<string, unknown>) || "$value" in (v as Record<string, unknown>))) {
        const raw = String((v as Record<string, unknown>).value || (v as Record<string, unknown>).$value);
        result.push({ name: k, resolved: raw.startsWith("{") ? resolveRef(raw, d) : raw });
      } else if (v && typeof v === "object") {
        for (const item of collectLeaves(v as Record<string, unknown>, d)) {
          result.push({ name: k + " " + item.name, resolved: item.resolved });
        }
      }
    }
    return result;
  }

  function loadFont(family: string) {
    const name = family.split(",")[0].trim().replace(/['"]/g, "");
    if (document.fonts.check(`1em "${name}"`)) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${name.replace(/ /g, "+")}:wght@100..900&display=swap`;
    document.head.appendChild(link);
  }

  function setActiveFont(fontValue: string) {
    activeFont = fontValue;
    loadFont(fontValue);
  }

  function fontShortName(family: string): string {
    return family.split(",")[0].trim().replace(/['"]/g, "");
  }

  function findFontFamilies(d: Record<string, unknown>): { name: string; value: string }[] {
    const typo = d.typography as Record<string, unknown> | undefined;
    if (!typo) return [];
    const ff = typo.fontFamily as Record<string, unknown> | undefined;
    if (!ff) return [];
    const result: { name: string; value: string }[] = [];
    for (const [k, v] of Object.entries(ff)) {
      if (v && typeof v === "object" && "value" in (v as Record<string, unknown>)) {
        result.push({ name: k, value: String((v as Record<string, unknown>).value) });
      }
    }
    return result;
  }

  function isHex(v: string) { return /^#[0-9A-Fa-f]{6,8}$/.test(v); }
  function isDimension(v: string) { return /^[\d.]+(px|rem|em|%|pt)$/.test(v); }
  function parseUnit(v: string) {
    const m = v.match(/^([\d.]+)(px|rem|em|%|pt)?$/);
    if (!m) return { val: 0, unit: "" };
    return { val: parseFloat(m[1]), unit: m[2] || "" };
  }
  function enhanceShadow(s: string) {
    if (s === "none") return "none";
    return s.replace(/rgba\(0,\s*0,\s*0,\s*[\d.]+\)/g, (m) => {
      const p = parseFloat(m.match(/[\d.]+$/)?.[0] || "0.1");
      return `rgba(0,0,0,${Math.min(p * 3, 0.5)})`;
    });
  }

  const fontFamilies = findFontFamilies(data);
  if (fontFamilies.length > 0 && !activeFont) {
    activeFont = fontFamilies[0].value;
    loadFont(activeFont);
  }

  function normCat(rawCatKey: string): { key: string; data: Record<string, unknown> } {
    const d = data[rawCatKey] as Record<string, unknown> | undefined;
    if (!d) return { key: rawCatKey, data: {} };
    if (rawCatKey === "border") return { key: "borderRadius", data: (d.radius || d) as Record<string, unknown> };
    if (rawCatKey === "shadow") return { key: "boxShadow", data: d };
    return { key: rawCatKey, data: d };
  }
</script>

<div class="space-y-8">
  {#each collectCategories(data) as rawCatKey}
    {@const n = normCat(rawCatKey)}
    {@const leaves = collectLeaves(n.data, data)}
    <div>
      <p class="text-[11px] uppercase tracking-widest text-gray-600 mb-4">{n.key}</p>
      <div class="space-y-3">
        {#if n.key === "color"}
          <div class="flex flex-wrap gap-1">
            {#each leaves as leaf (leaf.name)}
              {#if isHex(leaf.resolved)}
                <div class="flex flex-col items-center gap-1 p-2 rounded-lg bg-black/50 w-20" title={leaf.name}>
                  <div class="w-10 h-10 rounded-lg border" style="background:{leaf.resolved}; border-color:{leaf.resolved === '#FFFFFF' ? '#333' : 'transparent'}"></div>
                  <span class="text-[10px] text-gray-500 truncate w-full text-center font-mono">{leaf.resolved}</span>
                </div>
              {/if}
            {/each}
          </div>
        {:else if n.key === "typography"}
          {#if fontFamilies.length > 0}
            <div class="mb-4">
              <p class="text-[11px] text-gray-500 mb-2">Font family</p>
              <div class="flex flex-wrap gap-2">
                {#each fontFamilies as ff}
                  <button
                    onclick={() => setActiveFont(ff.value)}
                    class="px-4 py-3 rounded-xl border text-left transition-all {ff.value === activeFont ? 'bg-white border-white' : 'bg-black/50 border-[#1c1c1c] hover:border-[#444]'}"
                  >
                    <p class="text-sm mb-0.5 {ff.value === activeFont ? 'text-black' : 'text-white'}" style="font-family:{ff.value}">{fontShortName(ff.value)}</p>
                    <p class="text-[10px] {ff.value === activeFont ? 'text-black/60' : 'text-gray-600'}">{ff.name}</p>
                  </button>
                {/each}
              </div>
              {#if activeFont}
                <div class="mt-3 px-5 py-4 rounded-xl bg-black/50 border border-[#1c1c1c]" style="font-family:{activeFont}">
                  <p class="text-2xl text-white mb-1">Aa Bb Cc</p>
                  <p class="text-sm text-gray-400">The quick brown fox jumps over the lazy dog.</p>
                </div>
              {/if}
            </div>
          {/if}
          {#each leaves as leaf (leaf.name)}
            {#if leaf.name.startsWith("fontSize ")}
              {@const { val, unit } = parseUnit(leaf.resolved)}
              <div class="flex items-center gap-4">
                <span class="text-[10px] text-gray-600 w-16 shrink-0 text-right font-mono">{leaf.name.replace("fontSize ", "")}</span>
                <span style="font-size:{leaf.resolved}; font-family:{activeFont}" class="text-white truncate">The quick brown fox jumps over the lazy dog.</span>
                <span class="text-[10px] text-gray-600 font-mono">{leaf.resolved}</span>
              </div>
            {/if}
          {/each}
        {:else if n.key === "spacing"}
          <div class="space-y-2">
            {#each leaves as leaf (leaf.name)}
              {@const { val, unit } = parseUnit(leaf.resolved)}
              {#if val > 0}
                <div class="flex items-center gap-3">
                  <span class="text-[10px] text-gray-600 w-24 shrink-0 text-right">{leaf.name}</span>
                  <div class="h-3 bg-[#262626] rounded" style="width:min({val * (unit === 'rem' ? 2 : 4)}px, 300px)"></div>
                  <span class="text-[10px] text-gray-600 font-mono">{leaf.resolved}</span>
                </div>
              {/if}
            {/each}
          </div>
        {:else if n.key === "borderRadius"}
          <div class="flex flex-wrap gap-3">
            {#each leaves as leaf (leaf.name)}
              <div class="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-black/50 border border-[#1c1c1c] min-w-[70px]">
                <div class="w-10 h-10 bg-gray-600" style="border-radius:{leaf.resolved}"></div>
                <span class="text-[10px] text-gray-500">{leaf.name}</span>
              </div>
            {/each}
          </div>
        {:else if n.key === "boxShadow"}
          <div class="flex flex-wrap gap-3">
            {#each leaves as leaf (leaf.name)}
              <div class="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-white border min-w-[100px]">
                <div class="w-14 h-10 rounded" style="background:linear-gradient(135deg,#e5e5e5,#a3a3a3);box-shadow:{enhanceShadow(leaf.resolved)}"></div>
                <span class="text-[10px] text-gray-500">{leaf.name}</span>
              </div>
            {/each}
          </div>
        {:else if n.key === "opacity"}
          <div class="flex flex-wrap gap-3">
            {#each leaves as leaf (leaf.name)}
              <div class="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-black/50 border border-[#1c1c1c] min-w-[70px]">
                <div class="w-12 h-6 rounded bg-white" style="opacity:{leaf.resolved}"></div>
                <span class="text-[10px] text-gray-500">{leaf.name}</span>
              </div>
            {/each}
          </div>
        {:else}
          <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {#each leaves as leaf (leaf.name)}
              <div class="flex items-center gap-2 px-3 py-1.5 rounded bg-black/50">
                <span class="text-[10px] text-gray-600 truncate">{leaf.name}</span>
                <span class="text-[10px] text-gray-500 font-mono ml-auto">{leaf.resolved}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/each}
</div>
