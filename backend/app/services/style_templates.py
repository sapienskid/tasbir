"""Starter template packs per design language.

When a design system adopts a new ``style_language`` (Studio picker /
``POST /design-systems/{id}/style``), these templates give it an instant
usable library for the common format families — no LLM design needed for
first posts. They follow the same contract as every template: Jinja2,
``{{ width }}``/``{{ height }}`` canvas, ``data-slot`` copy slots,
``var(--color-*)`` tokens only, optional image/illustration slots.

Families a design system already has templates for are left untouched (the
user's library wins).
"""

from __future__ import annotations

import logging

# ruff: noqa: E501  # template HTML legitimately contains long CSS lines

log = logging.getLogger(__name__)

# style_language -> {family: html}. Templates use the standard context keys
# (kicker, headline, subhead, body, footer_left, footer_right, ground, width,
# height, has_image, illustration, tscale, ...).
STARTER_TEMPLATES: dict[str, dict[str, str]] = {
    "bold-modern": {
        "square": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: {{ width }}px; height: {{ height }}px; overflow: hidden; margin: 0;
  background: var(--color-bg); color: var(--color-text);
  font-family: var(--font-sans); -webkit-font-smoothing: antialiased;
  padding: {{ (width * 0.06) | round | int }}px;
}
body[data-ground="black"] { background: var(--color-bg-inverted); color: var(--color-text-inverted); }
.sheet { height: 100%; display: flex; flex-direction: column; }
.kicker {
  font-family: var(--font-sans); font-size: {{ (width * 0.022) | round | int }}px;
  font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--color-text-secondary);
}
.headline {
  font-family: var(--font-display); font-size: {{ (width * 0.09) | round | int }}px;
  font-weight: 700; letter-spacing: -0.02em; line-height: 0.98;
  margin-top: {{ (width * 0.04) | round | int }}px;
  max-width: {{ (width * 0.92) | round | int }}px;
}
.accent-rule {
  width: {{ (width * 0.16) | round | int }}px; height: {{ (width * 0.012) | round | int }}px;
  background: var(--color-accent); margin-top: {{ (width * 0.05) | round | int }}px;
}
.body {
  margin-top: {{ (width * 0.05) | round | int }}px; font-family: var(--font-serif);
  font-size: {{ (width * 0.028) | round | int }}px; line-height: 1.45;
  color: var(--color-text-secondary); max-width: {{ (width * 0.78) | round | int }}px;
}
.spacer { flex: 1; }
.footer {
  display: flex; justify-content: space-between; align-items: baseline;
  padding-top: {{ (width * 0.02) | round | int }}px;
}

.handle {
  font-size: {{ (width * 0.018) | round | int }}px; font-weight: 500;
  letter-spacing: 0.09em; text-transform: uppercase; color: var(--color-text-secondary);
}
</style>
</head>
<body {% if ground == "black" %}data-ground="black"{% endif %}>
  <div class="sheet">
    <div class="kicker" data-slot="kicker">{{ kicker }}</div>
    <h1 class="headline" data-slot="headline">{{ headline }}</h1>
    <div class="accent-rule"></div>
    {% if body %}
    <div class="body" data-slot="body">{{ body }}</div>
    {% elif subhead %}
    <div class="body" data-slot="subhead">{{ subhead }}</div>
    {% endif %}
    <div class="spacer"></div>
    {% if footer_right %}
    <div class="footer">
      <span class="handle" data-slot="footer_right">{{ footer_right }}</span>
    </div>
    {% endif %}
  </div>
</body>
</html>
""",
        "landscape": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: {{ width }}px; height: {{ height }}px; overflow: hidden; margin: 0;
  background: var(--color-bg); color: var(--color-text);
  font-family: var(--font-sans); -webkit-font-smoothing: antialiased;
  padding: {{ (height * 0.1) | round | int }}px {{ (width * 0.05) | round | int }}px;
}
body[data-ground="black"] { background: var(--color-bg-inverted); color: var(--color-text-inverted); }
.sheet { height: 100%; display: flex; align-items: stretch; }
.text { flex: 1 1 58%; display: flex; flex-direction: column; min-width: 0; }
.kicker {
  font-family: var(--font-sans); font-size: {{ (width * 0.014) | round | int }}px;
  font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--color-text-secondary);
}
.headline {
  font-family: var(--font-display); font-size: {{ (width * 0.055) | round | int }}px;
  font-weight: 700; letter-spacing: -0.02em; line-height: 1.0;
  margin-top: {{ (height * 0.06) | round | int }}px;
  max-width: {{ (width * 0.52) | round | int }}px;
}
.accent-rule {
  width: {{ (width * 0.12) | round | int }}px; height: {{ (height * 0.012) | round | int }}px;
  background: var(--color-accent); margin-top: {{ (height * 0.06) | round | int }}px;
}
.footer {
  margin-top: auto; display: flex; justify-content: space-between;
  align-items: baseline;
  padding-top: {{ (height * 0.03) | round | int }}px;
}
body[data-ground="black"] .footer { border-color: var(--color-border-inverted); }

.handle {
  font-size: {{ (width * 0.013) | round | int }}px; font-weight: 500;
  letter-spacing: 0.09em; text-transform: uppercase; color: var(--color-text-secondary);
}
.media { flex: 1 1 42%; min-width: 0; position: relative; overflow: hidden; }
.media .auto-photo, .media img { display: block; width: 100%; height: 100%; object-fit: cover; }
.media-empty { width: 100%; height: 100%; background: var(--color-text-tertiary); }
</style>
</head>
<body {% if ground == "black" %}data-ground="black"{% endif %}>
  <div class="sheet">
    <div class="text">
      <div class="kicker" data-slot="kicker">{{ kicker }}</div>
      <h1 class="headline" data-slot="headline">{{ headline }}</h1>
      <div class="accent-rule"></div>
      {% if footer_right %}
      <div class="footer">
        <span class="handle" data-slot="footer_right">{{ footer_right }}</span>
      </div>
      {% endif %}
    </div>
    {% if has_image %}
    <div class="media"><img data-image-key="0" alt=""/></div>
    {% else %}
    <div class="media"><div class="media-empty"></div></div>
    {% endif %}
  </div>
</body>
</html>
""",
    },
    "vibrant-pop": {
        "square": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: {{ width }}px; height: {{ height }}px; overflow: hidden; margin: 0;
  background: var(--color-bg); color: var(--color-text);
  font-family: var(--font-sans); -webkit-font-smoothing: antialiased;
  padding: {{ (width * 0.06) | round | int }}px;
}
body[data-ground="black"] { background: var(--color-bg-inverted); color: var(--color-text-inverted); }
.sheet { height: 100%; display: flex; flex-direction: column; }
.panel {
  flex: 1; border-radius: {{ (width * 0.05) | round | int }}px;
  padding: {{ (width * 0.07) | round | int }}px;
  display: flex; flex-direction: column;
  background: linear-gradient(145deg, var(--color-accent), var(--color-accent-secondary));
}
body[data-ground="black"] .panel { background: linear-gradient(145deg, var(--color-accent), var(--color-accent-secondary)); }
.panel .kicker, .panel .headline, .panel .body { color: var(--color-bg); }
.kicker {
  font-family: var(--font-sans); font-size: {{ (width * 0.024) | round | int }}px;
  font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--color-text-secondary);
}
.panel .kicker { color: var(--color-bg); }
.headline {
  font-family: var(--font-display); font-size: {{ (width * 0.075) | round | int }}px;
  font-weight: 800; letter-spacing: -0.015em; line-height: 1.0;
  margin-top: {{ (width * 0.04) | round | int }}px;
}
.panel .headline { color: var(--color-bg); }
.body {
  margin-top: {{ (width * 0.04) | round | int }}px;
  font-family: var(--font-serif); font-size: {{ (width * 0.026) | round | int }}px;
  line-height: 1.45; color: var(--color-text-secondary);
  max-width: {{ (width * 0.8) | round | int }}px;
}
.panel .body { color: var(--color-bg); }
.spacer { flex: 1; }
.footer {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-top: {{ (width * 0.04) | round | int }}px;
}

.handle {
  font-size: {{ (width * 0.018) | round | int }}px; font-weight: 700;
  letter-spacing: 0.09em; text-transform: uppercase; color: var(--color-text-secondary);
}
</style>
</head>
<body {% if ground == "black" %}data-ground="black"{% endif %}>
  <div class="sheet">
    <div class="panel">
      <span class="kicker" data-slot="kicker">{{ kicker }}</span>
      <h1 class="headline" data-slot="headline">{{ headline }}</h1>
      {% if body %}
      <div class="body" data-slot="body">{{ body }}</div>
      {% elif subhead %}
      <div class="body" data-slot="subhead">{{ subhead }}</div>
      {% endif %}
      <div class="spacer"></div>
    </div>
    {% if footer_right %}
    <div class="footer">
      <span class="handle" data-slot="footer_right">{{ footer_right }}</span>
    </div>
    {% endif %}
  </div>
</body>
</html>
""",
        "landscape": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: {{ width }}px; height: {{ height }}px; overflow: hidden; margin: 0;
  background: var(--color-bg); color: var(--color-text);
  font-family: var(--font-sans); -webkit-font-smoothing: antialiased;
  padding: {{ (height * 0.09) | round | int }}px {{ (width * 0.04) | round | int }}px;
}
body[data-ground="black"] { background: var(--color-bg-inverted); color: var(--color-text-inverted); }
.sheet { height: 100%; display: flex; gap: {{ (width * 0.03) | round | int }}px; }
.text {
  flex: 1 1 60%; border-radius: {{ (width * 0.03) | round | int }}px;
  background: linear-gradient(120deg, var(--color-accent), var(--color-accent-secondary));
  padding: {{ (height * 0.08) | round | int }}px {{ (width * 0.04) | round | int }}px;
  display: flex; flex-direction: column; min-width: 0;
}
.text .kicker, .text .headline, .text .body { color: var(--color-bg); }
.kicker {
  font-family: var(--font-sans); font-size: {{ (width * 0.014) | round | int }}px;
  font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--color-text-secondary);
}
.headline {
  font-family: var(--font-display); font-size: {{ (width * 0.048) | round | int }}px;
  font-weight: 800; letter-spacing: -0.015em; line-height: 1.0;
  margin-top: {{ (height * 0.05) | round | int }}px;
  max-width: {{ (width * 0.55) | round | int }}px;
}
.body {
  margin-top: {{ (height * 0.05) | round | int }}px;
  font-family: var(--font-serif); font-size: {{ (width * 0.02) | round | int }}px;
  line-height: 1.45; color: var(--color-text-secondary);
  max-width: {{ (width * 0.52) | round | int }}px;
}
.footer { margin-top: auto; display: flex; justify-content: space-between; align-items: baseline; }


.handle {
  font-size: {{ (width * 0.012) | round | int }}px; font-weight: 700;
  letter-spacing: 0.09em; text-transform: uppercase; color: var(--color-text-secondary);
}
.media { flex: 1 1 40%; min-width: 0; border-radius: {{ (width * 0.03) | round | int }}px; overflow: hidden; }
.media .auto-photo, .media img { display: block; width: 100%; height: 100%; object-fit: cover; }
.media-empty { width: 100%; height: 100%; background: var(--color-text-tertiary); }
</style>
</head>
<body {% if ground == "black" %}data-ground="black"{% endif %}>
  <div class="sheet">
    <div class="text">
      <span class="kicker" data-slot="kicker">{{ kicker }}</span>
      <h1 class="headline" data-slot="headline">{{ headline }}</h1>
      {% if body %}
      <div class="body" data-slot="body">{{ body }}</div>
      {% elif subhead %}
      <div class="body" data-slot="subhead">{{ subhead }}</div>
      {% endif %}
      {% if footer_right %}
      <div class="footer">
        <span class="handle" data-slot="footer_right">{{ footer_right }}</span>
      </div>
      {% endif %}
    </div>
    {% if has_image %}
    <div class="media"><img data-image-key="0" alt=""/></div>
    {% else %}
    <div class="media"><div class="media-empty"></div></div>
    {% endif %}
  </div>
</body>
</html>
""",
    },
}


async def seed_style_templates(
    db, ds_id: str, style_language: str, families: tuple[str, ...] = ("square", "landscape")
) -> list[str]:
    """Insert starter templates for a style into a design system.

    A starter is seeded for a family when the design system has no template
    tagged with this style yet — so restyling a DS (e.g. ``default`` with its
    Swiss pack) visibly changes template-first output instead of silently
    keeping the old templates. Families already carrying the style's tag are
    left untouched. Returns the ids of the templates created.
    """
    from app.db.repositories.templates import TemplateRepository
    from app.services.templates import scan_template_features

    pack = STARTER_TEMPLATES.get(style_language) or {}
    repo = TemplateRepository(db)
    existing = await repo.list(ds_id, include_inactive=True)

    def _tagged(fam: str) -> bool:
        return any(
            t.family == fam and style_language in {str(h).lower() for h in (t.hint_tags or [])}
            for t in existing
        )

    seeded: list[str] = []
    for fam in families:
        html = pack.get(fam)
        if not html or _tagged(fam):
            continue
        image_slots, has_logo = scan_template_features(html)
        base = f"{style_language}-{fam}"
        tid = base
        suffix = 2
        while await repo.get_by_id(tid):
            tid = f"{base}-{suffix}"
            suffix += 1
        await repo.create(
            {
                "id": tid,
                "design_system_id": ds_id,
                "name": f"{style_language.replace('-', ' ').title()} {fam}",
                "family": fam,
                "grounds": ["white", "black"],
                "categories": [],
                "hint_tags": ["style", style_language],
                "weight": 1.0,
                "description": f"Starter {fam} template for the {style_language} design language.",
                "html": html,
                "image_slots": image_slots,
                "has_logo_slot": has_logo,
                "source": "manual",
                "is_active": True,
            }
        )
        seeded.append(tid)
        existing = await repo.list(ds_id, include_inactive=True)
    if seeded:
        log.info("[style_templates] seeded %s starters for %s: %s", style_language, ds_id, seeded)
    return seeded


async def remove_other_style_templates(db, ds_id: str, style_language: str) -> list[str]:
    """Delete starter templates tagged with a different design language.

    Restyling a DS must not accumulate old styles' starters in the pool — the
    new style's templates take over (selection is style-scoped). Only templates
    carrying another style_language in their hint_tags are removed; user-authored
    templates are never touched. Returns the removed ids.
    """
    from app.db.repositories.templates import TemplateRepository
    from app.services.styles import STYLE_LANGUAGES

    repo = TemplateRepository(db)
    rows = await repo.list(ds_id, include_inactive=True)
    removed: list[str] = []
    for t in rows:
        tags = {str(h).lower() for h in (t.hint_tags or [])}
        if tags & (set(STYLE_LANGUAGES) - {style_language}):
            await repo.delete(t.id)
            removed.append(t.id)
    if removed:
        log.info("[style_templates] removed %s for %s: %s", style_language, ds_id, removed)
    return removed


__all__ = ["STARTER_TEMPLATES", "remove_other_style_templates", "seed_style_templates"]
