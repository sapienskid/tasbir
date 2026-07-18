from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.assets import AssetRepository

router = APIRouter()


@router.get("/{asset_key}")
async def get_asset(asset_key: str, db: AsyncSession = Depends(get_db)):
    repo = AssetRepository(db)
    asset = await repo.get_by_key(asset_key)
    if not asset:
        raise NotFoundError(f"Asset {asset_key} not found")
    return RedirectResponse(url=asset.url)


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
