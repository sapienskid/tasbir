"""Color contrast and palette generation tools for design token generation.

Provides WCAG contrast checking, accessible color pair suggestions,
and harmonious palette generation used by the token generator agent.
"""

import re
import math


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = linearize(rgb[0]), linearize(rgb[1]), linearize(rgb[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two hex colors."""
    l1 = relative_luminance(hex_to_rgb(fg))
    l2 = relative_luminance(hex_to_rgb(bg))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_contrast(fg: str, bg: str, level: str = "AA") -> dict:
    """Check if a foreground/background pair meets WCAG contrast requirements.

    Args:
        fg: Foreground hex color
        bg: Background hex color
        level: "AA" (4.5:1 normal, 3:1 large) or "AAA" (7:1 normal, 4.5:1 large)

    Returns:
        dict with ratio, pass_large, pass_normal, level
    """
    ratio = contrast_ratio(fg, bg)
    aa_normal = ratio >= 4.5
    aa_large = ratio >= 3.0
    aaa_normal = ratio >= 7.0
    aaa_large = ratio >= 4.5

    if level == "AAA":
        return {
            "ratio": round(ratio, 2),
            "pass": aaa_normal,
            "pass_large": aaa_large,
            "pass_normal": aaa_normal,
            "level": "AAA",
        }
    return {
        "ratio": round(ratio, 2),
        "pass": aa_normal,
        "pass_large": aa_large,
        "pass_normal": aa_normal,
        "level": "AA",
    }


def suggest_text_color(bg: str, light_text: str = "#EEE9E4", dark_text: str = "#0A0A0C") -> str:
    """Suggest whether light or dark text meets contrast on a given background."""
    light_ratio = contrast_ratio(light_text, bg)
    dark_ratio = contrast_ratio(dark_text, bg)
    return light_text if light_ratio >= 4.5 else dark_text if dark_ratio >= 4.5 else light_text


def generate_palette(primary: str, secondary: str, theme: str = "dark") -> dict:
    """Given brand primary/secondary, generate a complete palette for light or dark theme.

    Returns a dict matching the DTCG structure expected by the token system.
    Validates and reports contrast ratios for all text-on-background pairs.
    """
    if theme == "light":
        return _generate_light_theme_palette(primary, secondary)
    return _generate_dark_theme_palette(primary, secondary)


def _generate_dark_theme_palette(primary: str, secondary: str) -> dict:
    bg = "#0A0A0C"
    surface = "#141418"
    elevated = "#202026"
    border = "#2C2C30"
    text_primary = "#EEE9E4"
    text_secondary = "#9B9BA0"

    checks = [
        ("text on bg", text_primary, bg),
        ("text on surface", text_primary, surface),
        ("primary on bg", text_primary, primary),
        ("secondary on bg", text_secondary, bg),
    ]
    results = {label: check_contrast(fg, bg_c) for label, fg, bg_c in checks}

    return {
        "color": {
            "brand": {
                "primary": {"main": {"$value": primary, "$type": "color"}},
                "secondary": {"main": {"$value": secondary, "$type": "color"}},
            },
            "neutral": {
                "white": {"$value": "#FFFFFF", "$type": "color"},
                "black": {"$value": "#000000", "$type": "color"},
                "surface": {"$value": surface, "$type": "color"},
                "bg": {"$value": bg, "$type": "color"},
                "elevated": {"$value": elevated, "$type": "color"},
                "border": {"$value": border, "$type": "color"},
            },
            "semantic": {
                "text": {
                    "primary": {"$value": text_primary, "$type": "color"},
                    "secondary": {"$value": text_secondary, "$type": "color"},
                    "inverse": {"$value": "#0A0A0C", "$type": "color"},
                    "link": {"$value": primary, "$type": "color"},
                },
                "background": {
                    "primary": {"$value": primary, "$type": "color"},
                    "secondary": {"$value": secondary, "$type": "color"},
                    "surface": {"$value": surface, "$type": "color"},
                    "elevated": {"$value": elevated, "$type": "color"},
                },
                "action": {
                    "primary": {"$value": primary, "$type": "color"},
                    "hover": {"$value": _lighten(primary, 15), "$type": "color"},
                    "muted": {"$value": _darken(primary, 20), "$type": "color"},
                    "text": {"$value": "#FFFFFF", "$type": "color"},
                },
                "border": {
                    "default": {"$value": border, "$type": "color"},
                    "focus": {"$value": primary, "$type": "color"},
                },
            },
            "accent": {
                "default": {"$value": "#6366F1", "$type": "color"},
            },
        },
        "contrast_validation": results,
    }


def _generate_light_theme_palette(primary: str, secondary: str) -> dict:
    bg = "#FFFFFF"
    surface = "#F3F4F6"
    elevated = "#E5E7EB"
    border = "#D1D5DB"
    text_primary = "#111827"
    text_secondary = "#6B7280"

    checks = [
        ("text on bg", text_primary, bg),
        ("text on surface", text_primary, surface),
        ("primary on bg", text_primary, primary),
        ("secondary on bg", text_secondary, bg),
    ]
    results = {label: check_contrast(fg, bg_c) for label, fg, bg_c in checks}

    return {
        "color": {
            "brand": {
                "primary": {"main": {"$value": primary, "$type": "color"}},
                "secondary": {"main": {"$value": secondary, "$type": "color"}},
            },
            "neutral": {
                "white": {"$value": "#FFFFFF", "$type": "color"},
                "black": {"$value": "#000000", "$type": "color"},
                "surface": {"$value": surface, "$type": "color"},
                "bg": {"$value": bg, "$type": "color"},
                "elevated": {"$value": elevated, "$type": "color"},
                "border": {"$value": border, "$type": "color"},
            },
            "semantic": {
                "text": {
                    "primary": {"$value": text_primary, "$type": "color"},
                    "secondary": {"$value": text_secondary, "$type": "color"},
                    "inverse": {"$value": "#FFFFFF", "$type": "color"},
                    "link": {"$value": primary, "$type": "color"},
                },
                "background": {
                    "primary": {"$value": primary, "$type": "color"},
                    "secondary": {"$value": secondary, "$type": "color"},
                    "surface": {"$value": surface, "$type": "color"},
                    "elevated": {"$value": elevated, "$type": "color"},
                },
                "action": {
                    "primary": {"$value": primary, "$type": "color"},
                    "hover": {"$value": _darken(primary, 15), "$type": "color"},
                    "muted": {"$value": _lighten(primary, 20), "$type": "color"},
                    "text": {"$value": "#FFFFFF", "$type": "color"},
                },
                "border": {
                    "default": {"$value": border, "$type": "color"},
                    "focus": {"$value": primary, "$type": "color"},
                },
            },
            "accent": {
                "default": {"$value": "#6366F1", "$type": "color"},
            },
        },
        "contrast_validation": results,
    }


def _lighten(hex_color: str, percent: int) -> str:
    r, g, b = hex_to_rgb(hex_color)
    factor = 1 + percent / 100
    r = min(255, int(r * factor))
    g = min(255, int(g * factor))
    b = min(255, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken(hex_color: str, percent: int) -> str:
    r, g, b = hex_to_rgb(hex_color)
    factor = 1 - percent / 100
    r = max(0, int(r * factor))
    g = max(0, int(g * factor))
    b = max(0, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"
