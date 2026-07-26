"""DTCG token format conversion — internal ↔ W3C standard format.
Converts design tokens to Tailwind CSS config for runtime injection.
"""

import json


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (ValueError, IndexError):
        return (0, 0, 0)


def _luminance(rgb: tuple[int, int, int]) -> float:
    def lin(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _get_value(v: dict) -> str | None:
    for k in ("value", "$value"):
        if k in v:
            return str(v[k])
    return None


def _flatten(obj: dict, prefix: str = "") -> dict[str, str]:
    """Walk nested token structure, collect leaf value entries."""
    result: dict[str, str] = {}
    for key, val in obj.items():
        path = f"{prefix}/{key}" if prefix else key
        if isinstance(val, dict):
            leaf = _get_value(val)
            if leaf is not None:
                result[path] = leaf
            else:
                result.update(_flatten(val, path))
    return result


def flatten_tokens(tokens: dict, prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    for key, val in tokens.items():
        path = f"{prefix}/{key}" if prefix else key
        if isinstance(val, dict):
            leaf = _get_value(val)
            if leaf is not None:
                result[path] = leaf
            else:
                result.update(_flatten(val, path))
    return result


def build_dtcg(flat_tokens: dict[str, str], group_name: str = "tasbir") -> dict:
    result: dict = {}
    for path, value in flat_tokens.items():
        parts = path.split("/")
        if parts[0] == group_name:
            parts = parts[1:]
        cur = result
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                cur[part] = {"$value": value}
            else:
                if part not in cur:
                    cur[part] = {}
                cur = cur[part]
    return {group_name: result}


def tokens_to_tailwind_config(tokens: dict) -> dict:
    """Convert design tokens → Tailwind CSS theme extension."""
    flat = _flatten(tokens)
    tw: dict = {
        "colors": {},
        "fontFamily": {},
        "fontSize": {},
        "fontWeight": {},
        "lineHeight": {},
        "letterSpacing": {},
        "spacing": {},
        "borderRadius": {},
        "boxShadow": {},
        "opacity": {},
    }

    for path, value in flat.items():
        parts = path.lower().split("/")

        # Skip nested color taxonomies (neutral, semantic) — flat keys are already extracted
        if "color" in parts and len(parts) > 2:
            continue

        if any(r in parts for r in ("shadow", "boxshadow")):
            tw["boxShadow"][parts[-1]] = value
        elif "opacity" in parts:
            tw["opacity"][parts[-1]] = value
        elif any(r in parts for r in ("radius", "rounded", "borderradius")):
            tw["borderRadius"][parts[-1]] = value
        elif "color" in parts or "colors" in parts:
            tw["colors"][parts[-1]] = value
        elif any(f in parts for f in ("fontfamily", "family")):
            tw["fontFamily"][parts[-1]] = value.split(",") if "," in value else [value]
        elif "fontsize" in parts:
            tw["fontSize"][parts[-1]] = value
        elif "fontweight" in parts:
            tw["fontWeight"][parts[-1]] = int(value) if value.isdigit() else value
        elif "lineheight" in parts:
            tw["lineHeight"][parts[-1]] = float(value) if value.replace(".", "", 1).isdigit() else value
        elif "letterspacing" in parts:
            tw["letterSpacing"][parts[-1]] = value
        elif any(s in parts for s in ("spacing", "padding", "gap", "scale")):
            tw["spacing"][parts[-1]] = value

    return {k: v for k, v in tw.items() if v}


def tokens_to_css_variables(tokens: dict) -> str:
    """Generate :root CSS variables from design tokens."""
    flat = _flatten(tokens)
    if not flat:
        return ""
    lines = [":root {"]
    for path, value in sorted(flat.items()):
        var_name = "--" + path.lower().replace("/", "-")
        lines.append(f"  {var_name}: {value};")
    lines.append("}")
    return "\n".join(lines)


def _build_google_fonts_url(font_families: dict[str, list[str]] | dict[str, str]) -> str:
    """Build Google Fonts CDN URL from font families defined in tokens.

    Maps token key → font family name. Generates a URL with variable
    weight ranges suitable for headings and body text.
    """
    families: list[str] = []
    seen: set[str] = set()

    weight_map = {
        "sans": "wght@300;400;500;600;700;800",
        "serif": "ital,wght@0,400;0,700;1,400;1,700",
        "display": "ital,wght@0,400;0,700;1,400;1,700",
        "mono": "wght@400;500;600",
        "heading": "ital,wght@0,400;0,700;1,400;1,700",
        "body": "wght@300;400;500;600;700;800",
    }

    for key, val in font_families.items():
        if isinstance(val, list):
            name = val[0]  # first font is the preferred one
        elif isinstance(val, str):
            name = val
        else:
            continue

        if name and name not in seen and name not in ("inherit", "system-ui"):
            seen.add(name)
            encoded = name.replace(" ", "+")
            weights = weight_map.get(key, "wght@400;700")
            families.append(f"family={encoded}:{weights}")

    if not families:
        return (
            "https://fonts.googleapis.com/css2?"
            "family=Instrument+Serif:ital@0;1"
            "&family=Inter:wght@300;400;500;600;700;800"
            "&family=JetBrains+Mono:wght@400;500&display=swap"
        )

    return "https://fonts.googleapis.com/css2?" + "&".join(families) + "&display=swap"


def _resolve_ref(value: str, tree: dict) -> str:
    """Resolve DTCG references like {color.neutral.black} to actual values.

    Iterates the tree following the path specified in the reference.
    """
    if not value.startswith("{") or not value.endswith("}"):
        return value
    path = value.strip("{}").split(".")
    cur = tree
    for part in path:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return value  # can't resolve, return as-is
    if isinstance(cur, dict):
        val = _get_value(cur)
        if val:
            return _resolve_ref(val, tree)
    return str(cur)


def _extract_semantic_colors(color_dict: dict, tree: dict) -> dict[str, str]:
    """Extract flat primary/secondary/etc from color.semantic if present.

    Returns dict like {"primary": "#000000", "secondary": "#ffffff", ...}
    """
    semantic = color_dict.get("semantic", {})
    if not isinstance(semantic, dict):
        return {}
    result = {}
    for key in ("primary", "secondary", "accent", "background", "surface", "text", "muted", "action"):
        entry = semantic.get(key, {})
        if isinstance(entry, dict):
            val = _get_value(entry)
            if val:
                result[key] = _resolve_ref(val, tree)
    return result


def _merge_brand_into_tokens(tokens: dict, brand: dict | None) -> dict:
    """Merge brand colors + default palette into tokens dict so Tailwind config always has colors."""
    merged = dict(tokens) if tokens else {}

    # Resolve DTCG references ({color.neutral.black} → #000000) in the full tree
    merged = _resolve_tree(merged)

    if "color" not in merged:
        merged["color"] = {}
    color = merged["color"]

    # Extract semantic colors (color.semantic.primary) into flat form (color.primary)
    semantic_flat = _extract_semantic_colors(color, merged)
    for k, v in semantic_flat.items():
        if k not in color or not _get_value(color.get(k, {})):
            color[k] = {"$value": v, "$type": "color"}

    # Brand metadata takes highest priority — overrides any token values
    brand_primary = (brand or {}).get("primary_color", "")
    brand_secondary = (brand or {}).get("secondary_color", "")
    if brand_primary:
        color["primary"] = {"$value": brand_primary}
    elif not _get_value(color.get("primary", {})):
        color["primary"] = {"$value": "#18181b"}
    if brand_secondary:
        color["secondary"] = {"$value": brand_secondary}
    elif not _get_value(color.get("secondary", {})):
        color["secondary"] = {"$value": "#fafafa"}

    # Inject sensible defaults for ALL token categories when missing
    merged = _inject_defaults(merged)

    return merged

    # Inject sensible defaults for ALL token categories when missing.
    # This ensures the LLM always has a complete design system to work with
    # regardless of whether DTCG tokens were loaded from the DB.
    merged = _inject_defaults(merged)

    return merged


def _resolve_tree(tree: dict) -> dict:
    """Walk tree and resolve all DTCG references ({path.to.value})."""
    result = {}
    for key, val in tree.items():
        if isinstance(val, dict):
            result[key] = _resolve_tree(val)
        elif isinstance(val, str):
            result[key] = _resolve_ref(val, tree)
        else:
            result[key] = val
    # Also resolve within top-level leaves
    for key in list(result.keys()):
        if isinstance(result[key], dict):
            leaf = _get_value(result[key])
            if leaf and leaf.startswith("{"):
                result[key] = {"value": _resolve_ref(leaf, tree), "$type": result[key].get("$type", "")}
    return result


def _inject_defaults(tokens: dict) -> dict:
    """Ensure ALL token categories have default values so the design system is complete."""
    defaults = {
        "fontFamily": {
            "sans": {"$value": "Inter, sans-serif"},
            "serif": {"$value": "Instrument Serif, serif"},
            "mono": {"$value": "JetBrains Mono, monospace"},
        },
        "fontSize": {
            "xs": {"$value": "0.75rem"},
            "sm": {"$value": "0.875rem"},
            "base": {"$value": "1rem"},
            "lg": {"$value": "1.125rem"},
            "xl": {"$value": "1.25rem"},
            "2xl": {"$value": "1.5rem"},
            "3xl": {"$value": "1.875rem"},
            "4xl": {"$value": "2.25rem"},
            "5xl": {"$value": "3rem"},
            "6xl": {"$value": "3.75rem"},
        },
        "fontWeight": {
            "light": {"$value": "300"},
            "normal": {"$value": "400"},
            "medium": {"$value": "500"},
            "semibold": {"$value": "600"},
            "bold": {"$value": "700"},
        },
        "lineHeight": {
            "none": {"$value": "1"},
            "tight": {"$value": "1.15"},
            "snug": {"$value": "1.35"},
            "normal": {"$value": "1.5"},
            "relaxed": {"$value": "1.625"},
        },
        "letterSpacing": {
            "tighter": {"$value": "-0.05em"},
            "tight": {"$value": "-0.025em"},
            "normal": {"$value": "0"},
            "wide": {"$value": "0.025em"},
            "wider": {"$value": "0.05em"},
            "widest": {"$value": "0.1em"},
        },
        "spacing": {
            "0": {"$value": "0"},
            "2": {"$value": "0.5rem"},
            "4": {"$value": "1rem"},
            "6": {"$value": "1.5rem"},
            "8": {"$value": "2rem"},
            "12": {"$value": "3rem"},
            "16": {"$value": "4rem"},
        },
        "borderRadius": {
            "none": {"$value": "0"},
            "sm": {"$value": "0.125rem"},
            "md": {"$value": "0.375rem"},
            "lg": {"$value": "0.5rem"},
            "xl": {"$value": "0.75rem"},
            "2xl": {"$value": "1rem"},
            "full": {"$value": "9999px"},
        },
        "boxShadow": {
            "sm": {"$value": "0 1px 2px 0 rgba(0,0,0,0.05)"},
            "md": {"$value": "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)"},
            "lg": {"$value": "0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)"},
            "xl": {"$value": "0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)"},
            "2xl": {"$value": "0 25px 50px -12px rgba(0,0,0,0.25)"},
        },
        "opacity": {
            "0": {"$value": "0"},
            "10": {"$value": "0.1"},
            "20": {"$value": "0.2"},
            "30": {"$value": "0.3"},
            "40": {"$value": "0.4"},
            "50": {"$value": "0.5"},
            "60": {"$value": "0.6"},
            "70": {"$value": "0.7"},
            "80": {"$value": "0.8"},
            "90": {"$value": "0.9"},
        },
    }

    for category, values in defaults.items():
        if category not in tokens:
            tokens[category] = {}
        for key, token_value in values.items():
            if key not in tokens[category] or not _get_value(tokens[category].get(key, {})):
                tokens[category][key] = token_value

    return tokens


def build_config_html(tokens: dict | None = None, brand: dict | None = None) -> str:
    """Generate a <style> + <script> block that injects design tokens.

    Merges brand colors into DTCG tokens so bg-primary, text-primary always work.
    Always generates a complete Tailwind config + Google Fonts + CSS vars.

    Produces:
    1. Google Fonts <link> tag (brand fonts or fallback Instrument Serif/Inter/JetBrains Mono)
    2. Tailwind CDN script
    3. Tailwind config with theme.extend from merged tokens
    4. :root CSS custom properties
    """
    merged = _merge_brand_into_tokens(tokens or {}, brand)
    config = tokens_to_tailwind_config(merged)
    css_vars = tokens_to_css_variables(merged)

    font_families = config.get("fontFamily", {})
    fonts_url = _build_google_fonts_url(font_families)

    parts: list[str] = []
    # Config MUST be set BEFORE Tailwind CDN loads — CDN reads tailwind.config
    # at startup and won't see it if set after.
    parts.append(f"""<script>
tailwind.config = {{
  theme: {{
    extend: {json.dumps(config)}
  }}
}}
</script>""")
    parts.append('<script src="https://cdn.tailwindcss.com"></script>')
    parts.append(f'<link rel="stylesheet" href="{fonts_url}">')
    if css_vars:
        parts.append(f"<style>\n{css_vars}\n</style>")

    return "\n".join(parts)


def tailwind_config_html(tokens: dict) -> str:
    """Backward compat — generates Tailwind config from DTCG tokens only."""
    return build_config_html(tokens=tokens)
