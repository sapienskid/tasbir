"""Socket.IO server for real-time task progress streaming.

Mount this alongside FastAPI via socketio.ASGIApp(sio, fastapi_app).

Architecture:
  Celery Worker → RedisManager(write_only=True) → Redis pub/sub
                                                    ↓
  FastAPI Socket.IO server (AsyncRedisManager)  → Browser clients

No DB polling. No SSE. Rooms are scoped per task_id.
"""

from socketio import AsyncRedisManager, AsyncServer
from app.config import get_settings

settings = get_settings()

sio = AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins or ["*"],
    client_manager=AsyncRedisManager(settings.redis_url),
)


@sio.event
async def connect(sid, environ, auth):
    pass


@sio.event
async def join(sid, data):
    """Client joins a per-task room to receive progress events."""
    room = data.get("room")
    if room:
        sio.enter_room(sid, room)


@sio.event
async def disconnect(sid):
    pass
