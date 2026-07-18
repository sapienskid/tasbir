"""MinIO/S3 storage service — stores and retrieves generated assets.

Uses the MinIO Python SDK with async-compatible pattern.
"""

from app.config import get_settings


async def get_minio_client():
    """Get a configured MinIO client (sync SDK, run in executor)."""
    from minio import Minio

    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    return client


async def ensure_bucket():
    """Create the asset bucket if it doesn't exist."""
    import asyncio

    client = await get_minio_client()
    settings = get_settings()
    bucket = settings.minio_bucket

    def _ensure():
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

    await asyncio.to_thread(_ensure)


async def upload_asset(
    key: str,
    data: bytes,
    content_type: str = "image/png",
) -> str:
    """Upload an asset to MinIO.

    Args:
        key: Object key (path-like, e.g., 'tasks/{task_id}/{format}.png').
        data: Binary file content.
        content_type: MIME type of the content.

    Returns:
        Public URL of the uploaded asset.
    """
    import asyncio

    client = await get_minio_client()
    settings = get_settings()

    await ensure_bucket()

    def _upload():
        client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=key,
            data=__import__("io").BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    await asyncio.to_thread(_upload)
    return f"/assets/{key}"


async def get_asset_url(key: str) -> str | None:
    """Get a presigned URL for an asset.

    Args:
        key: Object key.

    Returns:
        Presigned URL string, or None if not found.
    """
    import asyncio

    client = await get_minio_client()
    settings = get_settings()

    def _get_url():
        try:
            return client.get_presigned_url(
                "GET",
                bucket_name=settings.minio_bucket,
                object_name=key,
            )
        except Exception:
            return None

    return await asyncio.to_thread(_get_url)


async def delete_asset(key: str) -> bool:
    """Delete an asset from MinIO.

    Args:
        key: Object key.

    Returns:
        True if deleted, False if not found.
    """
    import asyncio

    client = await get_minio_client()
    settings = get_settings()

    def _delete():
        try:
            client.remove_object(settings.minio_bucket, key)
            return True
        except Exception:
            return False

    return await asyncio.to_thread(_delete)
