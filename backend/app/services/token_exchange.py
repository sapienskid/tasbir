"""DTCG token format conversion — internal ↔ W3C standard format.
Converts design tokens to Tailwind CSS config for runtime injection.
"""

import json


def _get_value(v: dict) -> str | None:
    for k in ("value", "$value"):
        if k in v:
            return str(v[k])
    return None


def _flatten(obj: dict, data: dict, prefix: str = "") -> dict[str, str]:
    """Walk nested token structure, collect leaf value entries."""
    result: dict[str, str] = {}
    for key, val in obj.items():
        path = f"{prefix}/{key}" if prefix else key
        if isinstance(val, dict):
            leaf = _get_value(val)
            if leaf is not None:
                result[path] = leaf
            else:
                result.update(_flatten(val, data, path))
    return result


# Keep old public API names
def flatten_tokens(tokens: dict, prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    for key, val in tokens.items():
        path = f"{prefix}/{key}" if prefix else key
        if isinstance(val, dict):
            leaf = _get_value(val)
            if leaf is not None:
                result[path] = leaf
            else:
                result.update(_flatten(val, tokens, path))
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
    """Convert design tokens → Tailwind CSS v4 theme extension."""
    flat = _flatten(tokens, tokens)
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

        if any(r in parts for r in ("shadow", "boxshadow")):
            name = parts[-1]
            tw["boxShadow"][name] = value
        elif "opacity" in parts:
            name = parts[-1]
            tw["opacity"][name] = value
        elif any(r in parts for r in ("radius", "rounded", "borderradius")):
            name = parts[-1]
            tw["borderRadius"][name] = value
        elif "color" in parts:
            name = parts[-1]
            tw["colors"][name] = value
        elif any(f in parts for f in ("fontfamily", "family")):
            name = parts[-1]
            tw["fontFamily"][name] = value
        elif "fontsize" in parts or (parts[-2] if len(parts) > 1 else "") == "fontsize":
            name = parts[-1]
            tw["fontSize"][name] = value
        elif "fontweight" in parts:
            name = parts[-1]
            tw["fontWeight"][name] = int(value) if value.isdigit() else value
        elif "lineheight" in parts:
            name = parts[-1]
            tw["lineHeight"][name] = float(value)
        elif "letterspacing" in parts:
            name = parts[-1]
            tw["letterSpacing"][name] = value
        elif any(s in parts for s in ("spacing", "padding", "gap", "scale")):
            name = parts[-1]
            tw["spacing"][name] = value

    return {k: v for k, v in tw.items() if v}


def tailwind_config_html(tokens: dict) -> str:
    """Generate a <script> tag that sets Tailwind CSS v4 theme config.
    
    The LLM designer can just use standard Tailwind utility classes.
    This script maps the design token values into the Tailwind theme
    so classes like `bg-primary`, `font-sans`, `rounded-md` resolve
    to the token-defined values.
    """
    config = tokens_to_tailwind_config(tokens)
    return f"""<script>
tailwind.config = {{
  theme: {{
    extend: {json.dumps(config)}
  }}
}}
</script>"""
