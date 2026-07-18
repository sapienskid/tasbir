import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings

router = APIRouter()


def verify_ghost_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/ghost")
async def ghost_webhook(request: Request):
    settings = get_settings()
    if not settings.ghost_webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    signature = request.headers.get("x-ghost-signature", "")
    payload = await request.body()

    if not verify_ghost_webhook(payload, signature, settings.ghost_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = request.headers.get("x-ghost-event", "unknown")
    data = await request.json()

    if event == "post.published":
        from app.db.repositories.tasks import TaskRepository
        from app.db.session import create_pool
        from app.tasks.generate import generate_task

        pool = await create_pool(settings.database_url)
        async with pool() as session:
            repo = TaskRepository(session)
            post = data.get("post", {})

            source_data = {
                "content": post.get("html", ""),
                "title": post.get("title", ""),
                "excerpt": post.get("excerpt", ""),
                "tags": [t.get("name", "") for t in post.get("tags", [])],
                "source_url": post.get("url", ""),
                "feature_image": post.get("feature_image", ""),
                "source": "ghost",
            }

            task = await repo.create(source_data=source_data)
            generate_task.delay(str(task.id), source_data)

        await pool.close()

    return {"ok": True}
