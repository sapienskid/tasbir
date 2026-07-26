"""Celery tasks for brand creation and token generation."""

import asyncio
import uuid

from app.config import get_settings
from app.db.repositories.brands import BrandRepository
from app.db.repositories.tasks import TaskRepository
from app.db.session import create_pool
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def generate_token_task(self, task_id: str, brand_name: str, tone: str = "professional",
                        style: str = "modern", primary_color: str = "", secondary_color: str = ""):
    """Generate DTCG design tokens via LLM and store in the database."""
    settings = get_settings()

    async def _run():
        engine, pool = await create_pool(settings.database_url)
        try:
            async with pool() as session:
                await TaskRepository(session).update_status(
                    task_id=uuid.UUID(task_id), status="running", progress=10,
                )
        finally:
            await engine.dispose()

        try:
            from app.services.llm import call_llm

            system_prompt = (
                "You are a design token generator. Generate DTCG-format design tokens "
                "for the given brand. Use nested objects with 'value' and 'type'. "
                "Include: color (neutral palette + semantic colors), "
                "typography (fontFamily with sans, serif, mono, display variants; "
                "fontSize scale; fontWeight; lineHeight; letterSpacing), "
                "spacing (scale + layout gaps), borderRadius, boxShadow, and opacity. "
                "Return ONLY valid JSON with no markdown fences."
            )
            user_prompt = (
                f"Brand name: {brand_name}\n"
                f"Tone: {tone}\n"
                f"Style: {style}\n"
                f"Primary color: {primary_color or 'auto'}\n"
                f"Secondary color: {secondary_color or 'auto'}\n"
                f"Generate a complete set of design tokens."
            )
            response = await call_llm(
                "token_generator", system_prompt, user_prompt, temperature=0.3, max_tokens=8192,
            )

            if not response.strip():
                raise RuntimeError("LLM returned empty response")

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                cleaned = cleaned.rsplit("```", 1)[0].strip()

            import json
            data = json.loads(cleaned)

            engine2, pool2 = await create_pool(settings.database_url)
            try:
                async with pool2() as session:
                    from app.models.tokens import DesignToken
                    token = DesignToken(name=brand_name.lower(), data=data, source="ai-generated")
                    session.add(token)
                    await session.commit()
                    await session.refresh(token)

                    await TaskRepository(session).update_status(
                        task_id=uuid.UUID(task_id), status="completed", progress=100,
                        result={"token_id": str(token.id), "name": token.name},
                    )
            finally:
                await engine2.dispose()

        except Exception as e:
            engine2, pool2 = await create_pool(settings.database_url)
            try:
                async with pool2() as session:
                    await TaskRepository(session).update_status(
                        task_id=uuid.UUID(task_id), status="failed", error=str(e), progress=100,
                    )
            finally:
                await engine2.dispose()

    asyncio.run(_run())


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def generate_brand_task(self, task_id: str, name: str, description: str, logo_url: str = ""):
    """Generate a brand identity + design tokens via LLM.

    Creates a Brand record and a DesignToken record.
    The task is tracked via the generation_tasks table.
    """
    settings = get_settings()

    async def _run():
        engine, pool = await create_pool(settings.database_url)
        try:
            async with pool() as session:
                task_repo = TaskRepository(session)
                await task_repo.update_status(
                    task_id=uuid.UUID(task_id), status="running", progress=10,
                )
        finally:
            await engine.dispose()

        try:
            from app.services.llm import call_llm

            system_prompt = (
                "You are a design token generator. Generate DTCG-format design tokens "
                "for the given brand. Use nested objects with '$value' and '$type'. "
                "Include: color (primary, secondary, accent, neutral, semantic), "
                "typography (fontFamily with sans/serif/mono/display, fontSize scale, "
                "fontWeight, lineHeight, letterSpacing), spacing scale, borderRadius, "
                "boxShadow, and opacity. "
                "Also generate brand metadata: tone, primary_color, secondary_color, style_notes. "
                "Return ONLY valid JSON wrapped in ```json ... ``` fences with two top-level "
                "keys: 'brand' (metadata) and 'tokens' (DTCG tokens)."
            )
            user_prompt = (
                f"Brand name: {name}\n"
                f"Description: {description}\n"
                f"Generate a complete brand identity with DTCG design tokens."
            )

            response = await call_llm(
                "token_generator", system_prompt, user_prompt, temperature=0.3, max_tokens=8192,
            )

            import json

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                cleaned = cleaned.rsplit("```", 1)[0].strip()

            data = json.loads(cleaned)
            brand_meta = data.get("brand", {})
            tokens = data.get("tokens", {})

            engine2, pool2 = await create_pool(settings.database_url)
            try:
                async with pool2() as session:
                    brand_repo = BrandRepository(session)
                    brand_data = {
                        "tone": brand_meta.get("tone", "professional"),
                        "primary_color": brand_meta.get("primary_color", "#000000"),
                        "secondary_color": brand_meta.get("secondary_color", "#ffffff"),
                        "style_notes": brand_meta.get("style_notes", ""),
                        "logo_url": logo_url,
                        "tokens": tokens,
                    }
                    brand = await brand_repo.create(
                        name=name, description=description, data=brand_data,
                    )

                    task_repo = TaskRepository(session)
                    await task_repo.update_status(
                        task_id=uuid.UUID(task_id), status="completed", progress=100,
                        result={"brand_id": str(brand.id), "name": name},
                    )
            finally:
                await engine2.dispose()

        except Exception as e:
            engine2, pool2 = await create_pool(settings.database_url)
            try:
                async with pool2() as session:
                    await TaskRepository(session).update_status(
                        task_id=uuid.UUID(task_id), status="failed", error=str(e), progress=100,
                    )
            finally:
                await engine2.dispose()

    asyncio.run(_run())
