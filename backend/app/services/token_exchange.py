"""DTCG token format conversion — internal ↔ W3C standard format.
Converts design tokens to Tailwind CSS config for runtime injection.
"""

import json
from pathlib import Path


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

        # Use the last meaningful segment as the token name.
        # Paths may include a group prefix (e.g. "tasbir/color/primary").
        name = parts[-1]

        if any(r in parts for r in ("shadow", "boxshadow")):
            tw["boxShadow"][name] = value
        elif "opacity" in parts:
            tw["opacity"][name] = value
        elif any(r in parts for r in ("radius", "rounded", "borderradius")):
            tw["borderRadius"][name] = value
        elif "color" in parts or "colors" in parts:
            tw["colors"][name] = value
        elif any(f in parts for f in ("fontfamily", "family")):
            tw["fontFamily"][name] = value.split(",") if "," in value else [value]
        elif "fontsize" in parts:
            tw["fontSize"][name] = value
        elif "fontweight" in parts:
            tw["fontWeight"][name] = int(value) if value.isdigit() else value
        elif "lineheight" in parts:
            tw["lineHeight"][name] = float(value) if value.replace(".", "", 1).isdigit() else value
        elif "letterspacing" in parts:
            tw["letterSpacing"][name] = value
        elif any(s in parts for s in ("spacing", "padding", "gap", "scale")):
            tw["spacing"][name] = value

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


def _resolve_ref(value: str, tree: dict, _depth: int = 0) -> str:
    """Resolve DTCG references like {color.neutral.black} to actual values.

    Iterates the tree following the path specified in the reference.
    Protects against circular references via _depth counter.
    Returns fallback hex color if reference cannot be resolved.
    """
    if _depth > 10:
        return "#000000"
    if not value.startswith("{") or not value.endswith("}"):
        return value
    path = value.strip("{}").split(".")
    cur = tree
    for part in path:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return "#6366f1"  # fallback accent color
    if isinstance(cur, dict):
        val = _get_value(cur)
        if val:
            return _resolve_ref(val, tree, _depth + 1)
    return str(cur) if not str(cur).startswith("{") else "#6366f1"


def _extract_semantic_colors(color_dict: dict, tree: dict) -> dict[str, str]:
    """Walk color.semantic tree recursively and flatten all leaf values.

    Returns dict like {"primary": "#000000", "secondary": "#ffffff", ...}
    using the deepest meaningful key name.
    """
    semantic = color_dict.get("semantic", {})
    if not isinstance(semantic, dict):
        return {}

    flat = _flatten(semantic)
    result = {}
    for path, value in flat.items():
        resolved = _resolve_ref(value, tree)
        parts = path.split("/")
        name = parts[-1]
        # Skip generic category names
        if name in ("default", "background", "text", "action", "border", "surface", "muted"):
            if len(parts) >= 2:
                name = parts[-2]
        result[name] = resolved
    return result


def _merge_brand_into_tokens(tokens: dict, brand: dict | None) -> dict:
    """Resolve references and add category defaults. Leave colors as-is."""
    merged = dict(tokens) if tokens else {}
    merged = _resolve_tree(merged)

    merged = _inject_defaults(merged)
    return merged


def _resolve_tree(tree: dict, _root: dict | None = None) -> dict:
    """Walk tree and resolve all DTCG references ({path.to.value}).

    Uses the ROOT tree (passed as _root) for reference resolution so
    cross-references like {color.brand.primary.main} work correctly.
    """
    if _root is None:
        _root = tree
    result = {}
    for key, val in tree.items():
        if isinstance(val, dict):
            result[key] = _resolve_tree(val, _root)
        elif isinstance(val, str):
            result[key] = _resolve_ref(val, _root)
        else:
            result[key] = val
    for key in list(result.keys()):
        if isinstance(result[key], dict):
            leaf = _get_value(result[key])
            if leaf and leaf.startswith("{"):
                result[key] = {"value": _resolve_ref(leaf, _root), "$type": result[key].get("$type", "")}
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


def _compile_tailwind(theme_css: str) -> str:
    """Compile @theme CSS into full Tailwind utility CSS using standalone CLI.

    Runs the tailwindcss standalone binary with the given CSS as input.
    Falls back to empty string if CLI is unavailable.
    """
    import subprocess
    import tempfile
    import os
    import logging

    log = logging.getLogger(__name__)

    cli_paths = ["/usr/local/bin/tailwindcss", "/app/tailwindcss", "./tailwindcss"]
    cli = next((p for p in cli_paths if os.path.exists(p)), None)
    if not cli:
        return ""

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".css", delete=False) as f:
            f.write(theme_css)
            input_path = f.name
        output_path = input_path + ".compiled.css"

        result = subprocess.run(
            [cli, "--input", input_path, "--output", output_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and os.path.exists(output_path):
            css = open(output_path, "r").read()
            os.unlink(input_path)
            os.unlink(output_path)
            return css
        else:
            log.warning("Tailwind CLI failed: %s", result.stderr[:300])
    except Exception as exc:
        log.warning("Tailwind compile error: %s", exc)

    return ""


def _get_val(obj: dict, *keys: str) -> str | None:
    """Safely get a $value from a nested dict path."""
    cur = obj
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur.get("$value") or cur.get("value") if isinstance(cur, dict) else None


def _generate_theme_css(tokens: dict) -> str:
    """Build @theme CSS from design tokens using simple path-to-variable mapping.

    Extracts known paths from the token object and maps them to Tailwind v4
    @theme variables. This is explicit, not inferred from flattened paths.
    """
    vars_list: list[str] = []
    color = tokens.get("color", {})

    # ── Colors ─────────────────────────────────────────────────────
    # brand.primary.main → --color-primary (fallback: color.primary.$value)
    bp = _get_val(color, "brand", "primary", "main") or _get_val(color, "primary")
    if bp: vars_list.append(f"  --color-primary: {bp};")

    # brand.secondary.main → --color-secondary (fallback: color.secondary.$value)
    bs = _get_val(color, "brand", "secondary", "main") or _get_val(color, "secondary")
    if bs: vars_list.append(f"  --color-secondary: {bs};")

    # neutral.{key} → --color-{key}
    neutral = color.get("neutral", {})
    for key in ("white", "black", "bg", "surface", "elevated", "border"):
        val = _get_val(neutral, key)
        if val: vars_list.append(f"  --color-{key}: {val};")

    # accent.default → --color-accent
    ac = _get_val(color, "accent", "default")
    if ac: vars_list.append(f"  --color-accent: {ac};")

    # semantic.text.primary → --color-text
    tp = _get_val(color, "semantic", "text", "primary")
    if tp: vars_list.append(f"  --color-text: {tp};")

    # semantic.text.secondary → --color-text-secondary
    ts = _get_val(color, "semantic", "text", "secondary")
    if ts: vars_list.append(f"  --color-text-secondary: {ts};")

    # ── Typography ─────────────────────────────────────────────────
    # typography.fontFamily.{name} → --font-{name}
    for name in ("sans", "serif", "mono"):
        val = _get_val(tokens, "typography", "fontFamily", name)
        if val: vars_list.append(f"  --font-{name}: {val};")

    # typography.fontSize.{name} → --text-{name}
    for name in ("xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl"):
        val = _get_val(tokens, "typography", "fontSize", name)
        if val: vars_list.append(f"  --text-{name}: {val};")

    # typography.fontWeight.{name} → --font-weight-{name}
    for name in ("light", "normal", "medium", "semibold", "bold"):
        val = _get_val(tokens, "typography", "fontWeight", name)
        if val: vars_list.append(f"  --font-weight-{name}: {val};")

    # typography.lineHeight.{name} → --leading-{name}
    for name in ("tight", "snug", "normal", "relaxed"):
        val = _get_val(tokens, "typography", "lineHeight", name)
        if val: vars_list.append(f"  --leading-{name}: {val};")

    # typography.letterSpacing.{name} → --tracking-{name}
    for name in ("tighter", "tight", "normal", "wide", "wider", "widest"):
        val = _get_val(tokens, "typography", "letterSpacing", name)
        if val: vars_list.append(f"  --tracking-{name}: {val};")

    # ── Spacing ────────────────────────────────────────────────────
    spacing = tokens.get("spacing", {})
    for name in ("0", "1", "2", "3", "4", "5", "6", "8", "10", "12", "16", "20"):
        val = _get_val(tokens, "spacing", name)
        if val: vars_list.append(f"  --spacing-{name}: {val};")

    # ── Border Radius ──────────────────────────────────────────────
    radius = tokens.get("borderRadius", {})
    for name in ("none", "sm", "md", "lg", "xl", "2xl", "full"):
        val = _get_val(tokens, "borderRadius", name)
        if val: vars_list.append(f"  --radius-{name}: {val};")

    # ── Box Shadow ─────────────────────────────────────────────────
    shadow = tokens.get("boxShadow", {})
    for name in ("sm", "md", "lg", "xl"):
        val = _get_val(tokens, "boxShadow", name)
        if val: vars_list.append(f"  --shadow-{name}: {val};")

    # ── Opacity ────────────────────────────────────────────────────
    opacity = tokens.get("opacity", {})
    for name in ("0", "10", "20", "30", "40", "50", "60", "70", "80", "90"):
        val = _get_val(tokens, "opacity", name)
        if val: vars_list.append(f"  --opacity-{name}: {val};")

    return "@import \"tailwindcss\";\n@theme {\n" + "\n".join(vars_list) + "\n}"


def build_config_html(tokens: dict | None = None, brand: dict | None = None) -> str:
    """Generate <style> blocks with FULL Tailwind CSS compiled from design tokens.
    """
    merged = _merge_brand_into_tokens(tokens or {}, brand)
    theme_css = _generate_theme_css(merged)

    parts: list[str] = []

    # Step 1: Full Tailwind CSS compiled with design tokens
    compiled = _compile_tailwind(theme_css)
    if compiled:
        parts.append(f"<style>\n{compiled}\n</style>")
    else:
        parts.append(f"<style>\n{theme_css}\n</style>")

    # Step 2: Google Fonts
    config = tokens_to_tailwind_config(merged)
    font_families = config.get("fontFamily", {})
    fonts_url = _build_google_fonts_url(font_families)
    parts.append(f'<link rel="stylesheet" href="{fonts_url}">')

    # Step 3: Fallback CSS custom properties
    css_vars = tokens_to_css_variables(merged)
    if css_vars:
        parts.append(f"<style>\n{css_vars}\n</style>")

    return "\n".join(parts)


def tailwind_config_html(tokens: dict) -> str:
    """Backward compat — generates Tailwind config from DTCG tokens only."""
    return build_config_html(tokens=tokens)
