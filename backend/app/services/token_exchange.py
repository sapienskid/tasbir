"""DTCG token format conversion — internal ↔ W3C standard format.

Design Tokens Community Group (DTCG) format is the W3C standard for
representing design tokens. This module converts between the internal
flat format and the hierarchical DTCG format.
"""



def flatten_tokens(dtcg_tokens: dict, prefix: str = "") -> dict[str, str]:
    """Flatten hierarchical DTCG tokens into a flat key-value map.

    Example:
        {"tasbir": {"color": {"primary": {"$value": "#0066cc"}}}}
        → {"tasbir/color/primary": "#0066cc"}

    Args:
        dtcg_tokens: Hierarchical DTCG token dictionary.
        prefix: Key prefix for recursion.

    Returns:
        Flat dictionary of token paths to values.
    """
    result: dict[str, str] = {}

    for key, value in dtcg_tokens.items():
        full_path = f"{prefix}/{key}" if prefix else key

        if isinstance(value, dict):
            if "$value" in value:
                result[full_path] = str(value["$value"])
            elif "$type" in value:
                # Skip type declarations, continue recursion on siblings
                for sub_key, sub_value in value.items():
                    if sub_key.startswith("$"):
                        continue
                    sub_path = f"{full_path}/{sub_key}" if full_path else sub_key
                    if isinstance(sub_value, dict) and "$value" in sub_value:
                        result[sub_path] = str(sub_value["$value"])
                    elif isinstance(sub_value, dict):
                        result.update(flatten_tokens({sub_key: sub_value}, full_path))
            else:
                result.update(flatten_tokens(value, full_path))

    return result


def build_dtcg(flat_tokens: dict[str, str], group_name: str = "tasbir") -> dict:
    """Build hierarchical DTCG tokens from a flat key-value map.

    Example:
        {"tasbir/color/primary": "#0066cc"}
        → {"tasbir": {"color": {"$type": "color",
            "primary": {"$value": "#0066cc"}}}}

    Args:
        flat_tokens: Flat dictionary of token paths to values.
        group_name: Root group name.

    Returns:
        Hierarchical DTCG token dictionary.
    """

    def _type_from_name(name: str) -> str:
        if "color" in name.lower():
            return "color"
        if "font" in name.lower() or "typography" in name.lower() or "family" in name.lower():
            return "fontFamily"
        if "size" in name.lower() or "spacing" in name.lower() or "padding" in name.lower():
            return "dimension"
        if "radius" in name.lower() or "rounded" in name.lower():
            return "dimension"
        if "shadow" in name.lower():
            return "shadow"
        return "string"

    def _set_nested(d: dict, path_parts: list[str], value: str):
        current = d
        for i, part in enumerate(path_parts):
            if i == len(path_parts) - 1:
                current[part] = {"$value": value}
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]
                if "$type" not in current:
                    current["$type"] = _type_from_name(part)

    result: dict = {}
    for path, value in flat_tokens.items():
        parts = path.split("/")
        if parts[0] == group_name:
            parts = parts[1:]
        _set_nested(result, parts, value)

    return {group_name: result}


def tokens_to_tailwind_config(tokens: dict) -> dict:
    """Convert DTCG tokens to a Tailwind CSS config extension.

    Args:
        tokens: DTCG token dictionary.

    Returns:
        Tailwind-compatible theme extension.
    """
    flat = flatten_tokens(tokens)
    tailwind: dict = {
        "colors": {},
        "fontFamily": {},
        "spacing": {},
        "borderRadius": {},
    }

    for path, value in flat.items():
        parts = path.lower().split("/")

        if "color" in parts:
            name = parts[-1]
            tailwind["colors"][name] = value
        elif any(f in parts for f in ("fontfamily", "typography", "family")):
            name = parts[-1]
            tailwind["fontFamily"][name] = value
        elif any(s in parts for s in ("spacing", "padding", "gap")):
            name = parts[-1]
            tailwind["spacing"][name] = value
        elif any(r in parts for r in ("radius", "rounded", "borderradius")):
            name = parts[-1]
            tailwind["borderRadius"][name] = value

    return {k: v for k, v in tailwind.items() if v}
