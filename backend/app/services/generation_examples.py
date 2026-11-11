"""Explicitly curated, brand-scoped editorial examples, stored in SQLite.

Private app_settings records survive task retention and are included in the
existing configuration export/import. No automatic learning from edits or QC.
"""

from __future__ import annotations

import hashlib
import logging

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.db.repositories.app_settings import AppSettingRepository
from app.models.app_setting import AppSetting
from app.services.generation_quality import parse_copy

log = logging.getLogger(__name__)
PREFIX = "generation.example."


class ApprovedExample(BaseModel):
    design_system_id: str
    category: str = ""
    format: str
    headline: str = Field(default="", max_length=200)
    subhead: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=1200)
    rationale: str = Field(min_length=1, max_length=1000)
    template_id: str = ""
    composition: str = Field(default="", max_length=30)
    task_id: str = ""


def example_id(task_id: str, fmt: str) -> str:
    return PREFIX + hashlib.sha256(f"{task_id}|{fmt}".encode()).hexdigest()[:32]


async def list_examples(session, design_system_id: str = "", category: str = "") -> list[dict]:
    query = select(AppSetting).where(AppSetting.key.startswith(PREFIX))
    if design_system_id:
        query = query.where(AppSetting.value["design_system_id"].as_string() == design_system_id)
    if category:
        query = query.where(AppSetting.value["category"].as_string() == category)
    rows = (
        (await session.execute(query.order_by(AppSetting.updated_at.desc()).limit(200)))
        .scalars()
        .all()
    )
    examples = []
    for row in rows:
        try:
            value = ApprovedExample.model_validate(row.value)
        except ValidationError:
            continue
        if design_system_id and value.design_system_id != design_system_id:
            continue
        if category and value.category != category:
            continue
        examples.append({"id": row.key, **value.model_dump()})
    return examples


async def curate_example(session, task, fmt: str, rationale: str) -> dict:
    entry = ((task.result or {}).get("platforms") or {}).get(fmt)
    if not entry:
        raise ValueError("This format has no generated result to approve")
    if task.status in ("pending", "running"):
        raise ValueError("Wait for generation to finish before curating an example")
    recipe = entry.get("recipe") or {}
    # Prefer persisted editor slots/recipe over the original generation copy.
    copy = {**parse_copy(entry.get("copy") or ""), **(recipe.get("copy") or {})}
    for key in ("headline", "subhead", "body"):
        if key in recipe:
            copy[key] = recipe[key]
    if not (copy.get("headline") or copy.get("body")):
        raise ValueError("This format has no structured copy to curate")
    source = task.source_data or {}
    value = ApprovedExample(
        design_system_id=recipe.get("design_system_id")
        or source.get("design_system_id")
        or "default",
        category=recipe.get("category")
        or (task.result or {}).get("strategic_brief", {}).get("category")
        or source.get("category")
        or "",
        format=fmt,
        headline=str(copy.get("headline") or "")[:200],
        subhead=str(copy.get("subhead") or "")[:200],
        body=str(copy.get("body") or "")[:1200],
        rationale=rationale.strip(),
        template_id=entry.get("template_id") or "",
        composition=str((entry.get("content_profile") or {}).get("composition") or "")[:30],
        task_id=task.id,
    )
    key = example_id(task.id, fmt)
    repo = AppSettingRepository(session)
    if await repo.get(key):
        await repo.update(key, value.model_dump())
    else:
        await repo.create(key, value.model_dump(), "Human-approved generation reference")
    return {"id": key, **value.model_dump()}


async def reference_examples(ds_id: str, category: str) -> list[dict]:
    from app.db.session import get_shared_session_factory

    try:
        pool = await get_shared_session_factory()
        async with pool() as session:
            examples = await list_examples(session, ds_id, category)
            examples = [row for row in examples if row["category"] == category]
        # No templates, HTML, media, tokens or unrelated brand fields enter prompts.
        limits = {"headline": 120, "subhead": 120, "body": 400, "rationale": 300}
        return [
            {
                **{key: row[key][:cap] for key, cap in limits.items()},
                "composition": row["composition"],
                "template_id": row["template_id"],
            }
            for row in examples[:3]
        ]
    except Exception as exc:
        log.warning("[generation-examples] unavailable: %s", exc)
        return []
