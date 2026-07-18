from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings

router = APIRouter()


@router.post("/penpot")
async def penpot_webhook(request: Request):
    settings = get_settings()
    auth_header = request.headers.get("authorization", "")
    expected = f"Bearer {settings.penpot_access_token}"

    if settings.penpot_access_token and auth_header != expected:
        raise HTTPException(status_code=401, detail="Invalid token")

    data = await request.json()

    event = data.get("event", "unknown")
    if event in ("token.updated", "token.created"):
        from sqlalchemy import select

        from app.db.session import create_pool
        from app.models.tokens import DesignToken

        pool = await create_pool(settings.database_url)
        async with pool() as session:
            token_data = data.get("data", {})
            token_name = token_data.get("name", "penpot-tokens")

            result = await session.execute(
                select(DesignToken).where(DesignToken.name == token_name)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.data = token_data.get("tokens", {})
                existing.version += 1
                existing.source = "penpot"
            else:
                token = DesignToken(
                    name=token_name,
                    data=token_data.get("tokens", {}),
                    source="penpot",
                )
                session.add(token)

            await session.commit()
        await pool.close()

    return {"ok": True}
