"""Uploads API — validate + return base64 media for post image slots."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.uploads import validate_upload

router = APIRouter()


@router.post("")
async def upload_media(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        mime, b64 = validate_upload(raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "filename": file.filename,
        "mime": mime,
        "size": len(raw),
        "data": b64,
    }
