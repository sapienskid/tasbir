from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "service": "tasbir",
    }
