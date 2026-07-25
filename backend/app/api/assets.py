from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.assets import AssetRepository

router = APIRouter()


@router.get("/{asset_key:path}")
async def get_asset(asset_key: str, db: AsyncSession = Depends(get_db)):
    repo = AssetRepository(db)
    asset = await repo.get_by_key(asset_key)
    if not asset:
        raise NotFoundError(f"Asset {asset_key} not found")

    from app.services.storage import get_asset_url
    url = await get_asset_url(asset_key)
    if url:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            return Response(content=resp.content, media_type=asset.content_type)

    return Response(content=b"", status_code=502)


@router.post("/upload")
async def upload_file(file: UploadFile):
    from app.services.storage import upload_asset
    import uuid
    ext = file.filename.split(".")[-1] if file.filename else "png"
    key = f"uploads/{uuid.uuid4()}.{ext}"
    data = await file.read()
    url = await upload_asset(key, data, content_type=file.content_type or "image/png")
    return {"key": key, "url": url}


@router.get("/{asset_key}/info")
async def get_asset_info(asset_key: str, db: AsyncSession = Depends(get_db)):
    repo = AssetRepository(db)
    asset = await repo.get_by_key(asset_key)
    if not asset:
        raise NotFoundError(f"Asset {asset_key} not found")
    return {
        "key": asset.key,
        "task_id": str(asset.task_id),
        "format_id": asset.format_id,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "url": asset.url,
        "created_at": asset.created_at.isoformat(),
    }
